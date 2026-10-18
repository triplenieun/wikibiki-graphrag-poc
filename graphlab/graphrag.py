"""실제 Neo4j 근거를 읽는 작은 GraphRAG 검색기. LLM은 Cypher를 만들지 않는다."""
import re
from time import perf_counter

from graphlab.db import graph_session, read, run


class RetrievalError(Exception):
    """사용자가 질문 또는 서비스 선택을 수정하면 해결할 수 있는 오류."""


SERVICES = """
MATCH (s:Lab:Service)
RETURN s{.id, .name, description: CASE WHEN s.description_source = 'document'
         THEN '' ELSE coalesce(s.description, '') END} AS service
ORDER BY s.id
LIMIT 201
""".strip()

CONTEXT = """
MATCH path=(target:Lab:Service {id: $service_id})-[:DEPENDS_ON*0..1]->(s:Lab:Service)
WHERE all(n IN nodes(path) WHERE n:Lab:Service)
RETURN s{.id, .name, description: CASE WHEN s.description_source = 'document'
         THEN '' ELSE coalesce(s.description, '') END} AS service, length(path) AS hops,
       [r IN relationships(path) | {source: startNode(r).id, target: endNode(r).id,
                                    type: type(r)}] AS dependencies
ORDER BY service.id, hops
LIMIT 201
""".strip()

IMPACT = """
MATCH path=(s:Lab:Service)-[:DEPENDS_ON*0..5]->(target:Lab:Service {id: $service_id})
WHERE all(n IN nodes(path) WHERE n:Lab:Service)
  AND (length(path) = 0 OR s <> target)
RETURN s{.id, .name, description: CASE WHEN s.description_source = 'document'
         THEN '' ELSE coalesce(s.description, '') END} AS service, length(path) AS hops,
       [r IN relationships(path) | {source: startNode(r).id, target: endNode(r).id,
                                    type: type(r)}] AS dependencies
ORDER BY hops, service.id
LIMIT 201
""".strip()

OWNERS = """
MATCH (s:Lab:Service)-[:OWNED_BY]->(t:Lab:Team)
WHERE s.id IN $service_ids
RETURN s.id AS service_id, t{.id, .name} AS team
ORDER BY service_id, team.id
LIMIT 201
""".strip()

DOCUMENTS = """
MATCH (d:Lab:Document)-[:DESCRIBES]->(s:Lab:Service)
WHERE s.id IN $service_ids
WITH d, s ORDER BY s.id
WITH d, collect(DISTINCT s.id) AS service_ids
RETURN d.id AS document_id, d.title AS title, d.source AS source,
       left(coalesce(d.body, ''), 6000) AS body, head(service_ids) AS service_id,
       service_ids,
       size(coalesce(d.body, '')) > 6000 AS truncated
ORDER BY document_id
LIMIT 31
""".strip()

SNAPSHOT_NODES = """
MATCH (n:Lab)
WHERE n:Service OR n:Team OR n:Document
RETURN n.id AS id, coalesce(n.name, n.title, n.id) AS label,
       CASE WHEN n:Service THEN 'Service' WHEN n:Team THEN 'Team'
            ELSE 'Document' END AS kind
ORDER BY id
LIMIT 201
""".strip()

SNAPSHOT_EDGES = """
MATCH (a:Lab)-[r:DEPENDS_ON|OWNED_BY|DESCRIBES]->(b:Lab)
WHERE a.id IN $node_ids AND b.id IN $node_ids
RETURN DISTINCT a.id AS source, b.id AS target, type(r) AS type
ORDER BY source, target, type
LIMIT 201
""".strip()


def _validate(question, service_id, intent):
    if not isinstance(question, str) or not question.strip():
        raise RetrievalError("질문을 입력하세요.")
    if len(question) > 2000:
        raise RetrievalError("질문은 2,000자 이내로 입력하세요.")
    if not isinstance(service_id, str) or len(service_id) > 200:
        raise RetrievalError("서비스 ID가 올바르지 않습니다.")
    if intent not in ("auto", "context", "impact"):
        raise RetrievalError("검색 방식은 auto, context, impact 중 하나여야 합니다.")


def resolve_service(question, service_id, services):
    """고유 ID와 현재 DB의 이름으로만 대상을 결정하며 모호한 선택은 거부한다."""
    if service_id:
        matches = [service for service in services if service["id"] == service_id]
        if not matches:
            raise RetrievalError("선택한 서비스가 DB에 없습니다. 서비스 목록을 새로고침하세요.")
        return matches[0]
    text = question.casefold()
    matches = []
    for service in services:
        name = str(service.get("name") or "").strip().casefold()
        aliases = {str(service["id"]).casefold(), name, name.replace("서비스", "").strip()}
        # auth-service → auth 등은 독립 영어 단어일 때만 매칭한다.
        aliases.add(str(service["id"]).casefold().removesuffix("-service"))
        found = False
        for alias in aliases - {""}:
            if re.fullmatch(r"[a-z0-9_-]+", alias):
                found |= bool(re.search(r"(?<![a-z0-9_-])" + re.escape(alias) + r"(?![a-z0-9_-])", text))
            else:
                found |= alias in text
        if found:
            matches.append(service)
    if len(matches) == 1:
        return matches[0]
    if matches:
        names = ", ".join(str(service.get("name") or service["id"]) for service in matches)
        raise RetrievalError(f"여러 서비스가 질문에 등장합니다 ({names}). 조회 기준 서비스를 선택하세요.")
    raise RetrievalError("질문에서 서비스를 찾지 못했습니다. 조회 기준 서비스를 선택하세요.")


def resolve_intent(question, intent):
    if intent != "auto":
        return intent
    compact = re.sub(r"\s+", "", question.casefold())
    return "impact" if any(word in compact for word in ("영향", "파급", "impact", "affected")) else "context"


def _bounded(rows, limit, kind):
    if len(rows) > limit:
        raise RetrievalError(f"{kind}가 실습 검색 한도({limit}개)를 넘었습니다. 더 작은 실습 데이터로 조회하세요.")
    return rows


def retrieve(question, service_id="", intent="auto"):
    """한 읽기 트랜잭션에서 대상, 경로, 담당팀, 문서를 읽고 실제 질의 기록을 반환한다."""
    _validate(question, service_id, intent)
    question = question.strip()
    started = perf_counter()

    def query(tx):
        trace = []

        def execute(title, cypher, **parameters):
            rows = run(tx, cypher, **parameters)
            trace.append({"title": title, "cypher": cypher, "parameters": parameters, "rows": rows})
            return rows

        services = [row["service"] for row in _bounded(execute("대상 서비스 확인", SERVICES), 200, "서비스")]
        service = resolve_service(question, service_id, services)
        selected_intent = resolve_intent(question, intent)
        scope_rows = _bounded(execute(
            "의존 방향으로 1홉 탐색" if selected_intent == "context" else "역방향으로 최대 5홉 영향 탐색",
            CONTEXT if selected_intent == "context" else IMPACT,
            service_id=service["id"],
        ), 200, "탐색 경로")
        scoped = {row["service"]["id"]: row["service"] for row in scope_rows}
        if not scoped:
            raise RetrievalError("대상 서비스가 조회 중 변경되었습니다. 다시 조회하세요.")
        ids = sorted(scoped)
        owners = _bounded(execute("검색 범위의 담당팀 확인", OWNERS, service_ids=ids), 200, "담당 관계")
        documents = _bounded(execute("검색 범위의 근거 문서 확인", DOCUMENTS, service_ids=ids), 30, "근거 문서")
        nodes = {key: {"id": key, "label": value.get("name") or key, "kind": "Service"} for key, value in scoped.items()}
        edges = set()
        facts = []
        for key in ids:
            item = scoped[key]
            if item.get("description"):
                facts.append(f"{item.get('name') or key}: {item['description']}")
        for row in scope_rows:
            for edge in row["dependencies"]:
                edges.add((edge["source"], edge["target"], edge["type"]))
        for source, target, relation in sorted(edges):
            facts.append(f"{nodes[source]['label']}는 {nodes[target]['label']}에 의존합니다.")
        if selected_intent == "impact":
            affected = [key for key in ids if key != service["id"]]
            if affected:
                names = ", ".join(nodes[key]["label"] for key in affected)
                facts.append(f"{service.get('name') or service['id']}에 대한 최대 5홉 의존 경로에서 확인된 잠재 영향 서비스: {names}. 실제 장애 발생 여부는 확인되지 않았습니다.")
            else:
                facts.append("최대 5홉 범위에 대상 서비스에 의존하는 다른 서비스가 없습니다. 전체 시스템의 영향 없음이 보장되는 것은 아닙니다.")
        for row in owners:
            team = row["team"]
            nodes[team["id"]] = {"id": team["id"], "label": team.get("name") or team["id"], "kind": "Team"}
            edges.add((row["service_id"], team["id"], "OWNED_BY"))
            facts.append(f"{nodes[row['service_id']]['label']} 담당팀: {team.get('name') or team['id']}.")
        sources = []
        for index, row in enumerate(documents, 1):
            source = {"id": f"D{index}", **row}
            sources.append(source)
            nodes[row["document_id"]] = {"id": row["document_id"], "label": row["title"] or row["document_id"], "kind": "Document"}
            for described_id in row.get("service_ids", [row["service_id"]]):
                edges.add((row["document_id"], described_id, "DESCRIBES"))
        return {
            "question": question, "service": service, "intent": selected_intent,
            "answer": None, "model": None, "sources": sources, "facts": facts,
            "graph": {"nodes": sorted(nodes.values(), key=lambda node: node["id"]),
                      "edges": [{"source": a, "target": b, "type": kind} for a, b, kind in sorted(edges)]},
            "trace": trace,
            "scope": "self_and_direct_dependencies" if selected_intent == "context" else "self_and_inbound_dependencies_up_to_5_hops",
        }

    with graph_session() as session:
        result = read(session, query)
    result["retrieval_ms"] = round((perf_counter() - started) * 1000)
    return result


def graph_snapshot():
    """화면의 전체 그래프도 fixture 대신 현재 Lab 그래프에서 읽는다."""
    def query(tx):
        nodes = run(tx, SNAPSHOT_NODES)
        shown = nodes[:200]
        edges = run(tx, SNAPSHOT_EDGES, node_ids=[node["id"] for node in shown])
        return {"nodes": shown, "edges": edges[:200], "truncated": len(nodes) > 200 or len(edges) > 200}

    with graph_session() as session:
        return read(session, query)
