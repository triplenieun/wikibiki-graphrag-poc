"""Versioned document changes with reference-counted, reviewed graph facts.

Document-owned DESCRIBES links always follow the document. Other graph facts
are removed only if this app created them and no document still supports them.
Unmarked legacy/manual relationships deliberately keep their independent life.
"""
from django.core import signing

from graphlab import ingestion
from graphlab.db import graph_session, read, run, write


class DocumentNotFound(ingestion.ReviewError):
    pass


LOCK = "MERGE (lock:Lab:IngestionLock {id: 'document-ingestion-lock'}) SET lock.version = coalesce(lock.version, 0) + 1"
FIELDS = ("id", "title", "body", "source")
RELATIONS = {
    "DESCRIBES": "MATCH (a:Lab:Document {id:$source_id}), (b:Lab:Service {id:$target_id}) MERGE (a)-[r:DESCRIBES]->(b) ON CREATE SET r.managed_by_documents=true",
    "DEPENDS_ON": "MATCH (a:Lab:Service {id:$source_id}), (b:Lab:Service {id:$target_id}) MERGE (a)-[r:DEPENDS_ON]->(b) ON CREATE SET r.managed_by_documents=true",
    "OWNED_BY": "MATCH (a:Lab:Service {id:$source_id}), (b:Lab:Team {id:$target_id}) MERGE (a)-[r:OWNED_BY]->(b) ON CREATE SET r.managed_by_documents=true",
}
REMOVE_FACT = {
    "DEPENDS_ON": "MATCH (:Lab:Service {id:$source_id})-[r:DEPENDS_ON]->(:Lab:Service {id:$target_id}) ",
    "OWNED_BY": "MATCH (:Lab:Service {id:$source_id})-[r:OWNED_BY]->(:Lab:Team {id:$target_id}) ",
}
REMOVE_UNSUPPORTED = """WHERE r.managed_by_documents = true AND NOT EXISTS {
    MATCH (a:Lab:Assertion) WHERE a.source_id=$source_id AND a.target_id=$target_id
      AND a.relation_type=$relation_type
} DELETE r"""
LEGACY_WARNING = "이 문서가 뒷받침하는 관계 중 기존·수동 등록 또는 생성 출처를 확인할 수 없는 관계가 있습니다. 문서를 수정·삭제해도 해당 서비스 간 관계와 담당팀 관계는 유지됩니다."


def _version(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ingestion.ReviewError("문서의 최신 version 값이 필요합니다. 목록을 새로고침하세요.")
    return value


def _state(tx, document_id):
    rows = run(tx, """MATCH (d:Lab:Document {id:$id})
        RETURN d.id AS id, coalesce(d.title,'') AS title, coalesce(d.body,'') AS body,
          coalesce(d.source,'') AS source, d.reviewed = true AS can_manage,
          coalesce(toString(d.updated_at),toString(d.created_at),'') AS updated_at,
          d.last_update_hash AS last_update_hash""", id=document_id)
    if not rows:
        raise DocumentNotFound("문서를 찾을 수 없습니다. 삭제되었는지 목록을 새로고침하세요.")
    document = rows[0]
    document["can_manage"] = bool(document["can_manage"])
    assertions = run(tx, """MATCH (a:Lab:Assertion {document_id:$id})
        RETURN a.source_id AS source_id,a.relation_type AS type,a.target_id AS target_id,a.evidence AS evidence
        ORDER BY source_id,type,target_id,evidence LIMIT 61""", id=document_id)
    if len(assertions) > 60:
        raise ingestion.ReviewError("문서 근거가 60개를 넘습니다. 관리자에게 데이터 점검을 요청하세요.")
    describes = run(tx, """MATCH (:Lab:Document {id:$id})-[:DESCRIBES]->(s:Lab:Service)
        RETURN s.id AS id ORDER BY id""", id=document_id)
    document["service_ids"] = [row["id"] for row in describes]
    document["version"] = ingestion._hash({"document": document, "relations": assertions})
    return document, assertions


def _require_manage(document):
    if not document["can_manage"]:
        raise ingestion.ReviewConflict("예제 문서는 읽기 전용입니다. 문서 등록으로 복사한 뒤 수정하세요.")


def _legacy_warnings(tx, edges):
    non_document = [edge for edge in edges if edge["type"] in REMOVE_FACT]
    if not non_document:
        return []
    protected = run(tx, """UNWIND $edges AS edge
        MATCH (s:Lab:Service {id:edge.source_id})-[r]->(t:Lab {id:edge.target_id})
        WHERE type(r)=edge.type AND coalesce(r.managed_by_documents,false)=false
        RETURN count(r) AS count""", edges=non_document)
    return [LEGACY_WARNING] if protected and protected[0]["count"] else []


def _detail(tx, document_id):
    document, edges = _state(tx, document_id)
    warnings = _legacy_warnings(tx, edges)
    # Old seed documents have direct links without assertions. They are visible,
    # but deliberately read-only and never receive an update review token.
    if not edges:
        edges = [{"source_id": document_id, "type": "DESCRIBES", "target_id": service_id,
                  "evidence": document["body"][:1000]} for service_id in document["service_ids"]]
    used = {edge[key] for edge in edges for key in ("source_id", "target_id")} - {document_id}
    nodes = [{**{key: node.get(key, "") for key in ("id", "kind", "name", "description")}, "existing": True}
             for node in ingestion._catalog(tx) if node["id"] in used]
    signed = {key: document[key] for key in FIELDS}
    signed.update(_operation="update", _base_version=document["version"])
    document.pop("last_update_hash", None)
    return {"document": document, "can_manage": document["can_manage"], "nodes": nodes,
            "relations": edges, "warnings": warnings,
            "review_token": signing.dumps(signed, salt=ingestion.SALT, compress=True) if document["can_manage"] else None}


def detail(document_id):
    ingestion._id(document_id)
    with graph_session() as session:
        return read(session, lambda tx: _detail(tx, document_id))


def listing(query="", offset="0", limit="50"):
    query = ingestion._text(query, "검색어", 200, False)
    try:
        offset, limit = int(offset), int(limit)
    except (ValueError, TypeError) as exc:
        raise ingestion.ReviewError("offset과 limit은 정수로 입력하세요.") from exc
    if offset < 0 or not 1 <= limit <= 100:
        raise ingestion.ReviewError("offset은 0 이상, limit은 1~100으로 입력하세요.")
    def fetch(tx):
        where = """MATCH (d:Lab:Document) WHERE toLower(coalesce(d.title,'')) CONTAINS toLower($query)
            OR toLower(coalesce(d.source,'')) CONTAINS toLower($query) OR d.id CONTAINS toLower($query) """
        total = run(tx, where + "RETURN count(d) AS total", query=query)[0]["total"]
        rows = run(tx, where + "RETURN d.id AS id ORDER BY coalesce(d.reviewed,false) DESC,coalesce(d.updated_at,d.created_at,datetime({epochMillis:0})) DESC,d.id SKIP $offset LIMIT $limit", query=query, offset=offset, limit=limit)
        documents = []
        for row in rows:
            document, edges = _state(tx, row["id"])
            document.pop("body")
            document.pop("last_update_hash", None)
            document["relation_count"] = len(edges) or len(document["service_ids"])
            documents.append(document)
        return {"documents": documents, "total": total, "offset": offset, "limit": limit, "has_more": offset + len(documents) < total}
    with graph_session() as session:
        return read(session, fetch)


def extract_update(document_id, payload):
    if not isinstance(payload, dict):
        raise ingestion.ReviewError("JSON 객체 형식으로 문서를 보내세요.")
    version = _version(payload.get("version"))
    previous = detail(document_id)
    _require_manage(previous["document"])
    if previous["document"]["version"] != version:
        raise ingestion.ReviewConflict("문서가 다른 화면에서 변경되었습니다. 최신 문서를 다시 열어 수정하세요.")
    result = ingestion.extract(payload, document_id=document_id, base_version=version)
    result["warnings"].extend(previous["warnings"])
    return result


def _withdraw(tx, document_id, edges):
    warnings = _legacy_warnings(tx, edges)
    run(tx, "MATCH (a:Lab:Assertion {document_id:$id}) DETACH DELETE a", id=document_id)
    run(tx, "MATCH (:Lab:Document {id:$id})-[r:DESCRIBES]->() DELETE r", id=document_id)
    seen = set()
    for edge in edges:
        key = (edge["source_id"], edge["type"], edge["target_id"])
        if edge["type"] not in REMOVE_FACT or key in seen:
            continue
        seen.add(key)
        run(tx, REMOVE_FACT[edge["type"]] + REMOVE_UNSUPPORTED,
            source_id=edge["source_id"], target_id=edge["target_id"], relation_type=edge["type"])
    return warnings


def _persist_review(tx, document, raw_nodes, raw_edges):
    nodes, edges, warnings = ingestion.normalize_review(document, raw_nodes, raw_edges, ingestion._catalog(tx))
    kinds = {node["id"]: node["kind"] for node in nodes}
    occupied = run(tx, "MATCH (n:Lab) WHERE n.id IN $ids RETURN n.id AS id,labels(n) AS labels", ids=list(kinds))
    for node in occupied:
        if set(node["labels"]) != {"Lab", kinds[node["id"]]}:
            raise ingestion.ReviewConflict(f"{node['id']}는 다른 종류의 기존 노드 ID입니다.")
    for edge in edges:
        if edge["type"] == "OWNED_BY":
            owners = run(tx, "MATCH (:Lab:Service {id:$id})-[:OWNED_BY]->(t) RETURN t.id AS id", id=edge["source_id"])
            if any(owner["id"] != edge["target_id"] for owner in owners):
                raise ingestion.ReviewConflict("다른 문서나 기존 그래프가 현재 담당팀을 유지하고 있습니다. 기존 담당팀 관계를 확인한 뒤 다시 수정하세요.")
    for kind, statement in (("Service", "MERGE (n:Lab {id:$id}) ON CREATE SET n:Service,n.name=$name,n.description=$description,n.description_source='document'"),
                            ("Team", "MERGE (n:Lab {id:$id}) ON CREATE SET n:Team,n.name=$name,n.description=$description,n.description_source='document'")):
        for node in nodes:
            if node["kind"] == kind:
                run(tx, statement, **{key: node[key] for key in ("id", "name", "description")})
    for edge in edges:
        run(tx, RELATIONS[edge["type"]], source_id=edge["source_id"], target_id=edge["target_id"])
        run(tx, """MERGE (a:Lab:Assertion {id:$id}) ON CREATE SET a.document_id=$document_id,
            a.source_id=$source_id,a.target_id=$target_id,a.relation_type=$relation_type,
            a.evidence=$evidence,a.created_at=datetime(),a.reviewed=true
            WITH a MATCH (d:Lab:Document {id:$document_id}) MERGE (d)-[:SUPPORTS]->(a)""",
            id="assertion-" + ingestion._hash([document["id"], edge]), document_id=document["id"],
            source_id=edge["source_id"], target_id=edge["target_id"], relation_type=edge["type"], evidence=edge["evidence"])
    return sorted({edge["target_id"] for edge in edges if edge["type"] == "DESCRIBES"}), warnings


def update(document_id, payload):
    ingestion._id(document_id)
    if not isinstance(payload, dict):
        raise ingestion.ReviewError("JSON 객체 형식으로 검토 결과를 보내세요.")
    signed = ingestion._review_document(payload.get("review_token"))
    if signed.get("_operation") != "update" or signed["id"] != document_id:
        raise ingestion.ReviewError("해당 문서의 수정 미리보기 토큰이 필요합니다.")
    version = _version(signed.get("_base_version"))
    document = {key: signed[key] for key in FIELDS}
    raw_nodes, raw_edges = payload.get("nodes"), payload.get("relations")
    ingestion.normalize_review(document, raw_nodes, raw_edges, [])
    operation_hash = ingestion._hash({"document": signed, "nodes": sorted(raw_nodes, key=lambda n: n["id"]),
        "relations": sorted(raw_edges, key=lambda e: (e["source_id"], e["type"], e["target_id"], e["evidence"]))})
    def commit(tx):
        run(tx, LOCK)
        old, edges = _state(tx, document_id)
        _require_manage(old)
        if old["last_update_hash"] == operation_hash:
            return {"document": {key: old[key] for key in (*FIELDS, "version")}, "created": False,
                    "service_ids": old["service_ids"], "warnings": [], "message": "이미 반영한 수정입니다. 중복 저장하지 않았습니다."}
        if old["version"] != version:
            raise ingestion.ReviewConflict("문서가 다른 화면에서 변경되었습니다. 최신 문서를 다시 열어 수정하세요.")
        warnings = _withdraw(tx, document_id, edges)
        service_ids, new_warnings = _persist_review(tx, document, raw_nodes, raw_edges)
        run(tx, """MATCH (d:Lab:Document {id:$id}) SET d.title=$title,d.body=$body,d.source=$source,
            d.updated_at=datetime(),d.document_hash=$document_hash,d.review_hash=$review_hash,
            d.last_update_hash=$review_hash,d.service_ids=$service_ids""", **document,
            document_hash=ingestion._hash(document), review_hash=operation_hash, service_ids=service_ids)
        updated, _ = _state(tx, document_id)
        return {"document": {key: updated[key] for key in (*FIELDS, "version")}, "created": False,
                "service_ids": service_ids, "warnings": warnings + new_warnings,
                "message": "문서와 검토한 관계를 수정했습니다. GraphRAG 검색에 바로 반영됩니다."}
    with graph_session() as session:
        return write(session, commit)


def delete(document_id, payload):
    ingestion._id(document_id)
    if not isinstance(payload, dict):
        raise ingestion.ReviewError("JSON 객체 형식으로 삭제 요청을 보내세요.")
    version = _version(payload.get("version"))
    def commit(tx):
        run(tx, LOCK)
        tombstone = run(tx, "MATCH (d:Lab:DocumentTombstone {id:$id}) RETURN d.deleted_version AS version", id=document_id)
        if tombstone:
            if tombstone[0]["version"] != version:
                raise ingestion.ReviewConflict("다른 버전의 문서가 삭제되었습니다. 목록을 새로고침하세요.")
            return {"deleted": True, "document_id": document_id, "warnings": [], "message": "이미 삭제한 문서입니다."}
        document, edges = _state(tx, document_id)
        _require_manage(document)
        if document["version"] != version:
            raise ingestion.ReviewConflict("문서가 변경되어 삭제하지 않았습니다. 최신 내용을 확인한 뒤 다시 삭제하세요.")
        warnings = _withdraw(tx, document_id, edges)
        run(tx, "MATCH (d:Lab:Document {id:$id}) DETACH DELETE d", id=document_id)
        # No original body/title remains. The reserved ID blocks an old signed
        # create draft from silently recreating a deliberately deleted document.
        run(tx, "CREATE (:Lab:DocumentTombstone {id:$id,deleted_version:$version,deleted_at:datetime()})", id=document_id, version=version)
        return {"deleted": True, "document_id": document_id, "warnings": warnings,
                "message": "문서와 해당 문서만 뒷받침하던 관리 관계를 삭제했습니다. GraphRAG 검색에 바로 반영됩니다."}
    with graph_session() as session:
        return write(session, commit)
