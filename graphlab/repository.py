"""Read queries over the lab graph. Relationships point in their stored direction."""
from graphlab.db import graph_session, read, run

SERVICE = """
MATCH (s:Lab:Service {id: $service_id})
OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Lab:Team)
RETURN s{.id, .name, .description} AS service, t{.id, .name} AS owner
"""


def list_services():
    with graph_session() as session:
        return read(session, lambda tx: run(tx, """
            MATCH (s:Lab:Service)
            OPTIONAL MATCH (s)-[:OWNED_BY]->(t:Lab:Team)
            RETURN s.id AS id, s.name AS name, s.description AS description,
                   t{.id, .name} AS owner
            ORDER BY s.id
        """))


def service_context(service_id):
    def retrieve(tx):
        rows = run(tx, SERVICE, service_id=service_id)
        if not rows:
            return None
        dependencies = run(tx, """
            MATCH (:Lab:Service {id: $service_id})-[:DEPENDS_ON]->(d:Lab:Service)
            OPTIONAL MATCH (d)-[:OWNED_BY]->(t:Lab:Team)
            RETURN d.id AS id, d.name AS name, d.description AS description,
                   t{.id, .name} AS owner
            ORDER BY d.id
        """, service_id=service_id)
        documents = run(tx, """
            MATCH (:Lab:Service {id: $service_id})-[:DEPENDS_ON*0..1]->(s:Lab:Service)
                  <-[:DESCRIBES]-(d:Lab:Document)
            WITH d, s ORDER BY s.id
            WITH d, collect(DISTINCT s.id) AS service_ids
            RETURN d.id AS id, d.title AS title, d.source AS source,
                   d.body AS body, head(service_ids) AS service_id, service_ids
            ORDER BY d.id
        """, service_id=service_id)
        return {
            **rows[0],
            "scope": "self_and_direct_dependencies",
            "dependencies": dependencies,
            "documents": documents,
        }

    with graph_session() as session:
        return read(session, retrieve)


def service_impact(service_id):
    def retrieve(tx):
        rows = run(tx, SERVICE, service_id=service_id)
        if not rows:
            return None
        affected = run(tx, """
            MATCH path=(s:Lab:Service)-[:DEPENDS_ON*1..5]->
                       (target:Lab:Service {id: $service_id})
            WHERE s <> target AND all(n IN nodes(path) WHERE n:Lab:Service)
            RETURN s.id AS id, s.name AS name, min(length(path)) AS hops
            ORDER BY hops, id
        """, service_id=service_id)
        return {
            "service": rows[0]["service"],
            "max_hops": 5,
            "affected_services": affected,
        }

    with graph_session() as session:
        return read(session, retrieve)
