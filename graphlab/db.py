"""Neo4j connection boundary, independent of Django ORM."""
from contextlib import contextmanager

from django.conf import settings
from neo4j import GraphDatabase, unit_of_work
from neo4j.exceptions import DriverError, Neo4jError


class GraphConnectionError(Exception):
    """A safe, user-facing message that never includes credentials."""


@contextmanager
def graph_session():
    if not settings.NEO4J_PASSWORD:
        raise GraphConnectionError(
            ".env의 NEO4J_PASSWORD를 설정하세요. .env.example을 복사해서 시작할 수 있습니다."
        )
    try:
        # One driver per operation keeps lifetime explicit in a learning app.
        # A production app can reuse one driver per worker process.
        with GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
            connection_timeout=5.0,
            connection_acquisition_timeout=5.0,
            max_transaction_retry_time=5.0,
        ) as driver:
            with driver.session(database=settings.NEO4J_DATABASE) as session:
                yield session
    except (Neo4jError, DriverError, OSError, ValueError) as exc:
        raise GraphConnectionError(
            "Neo4j 연결 또는 질의에 실패했습니다. docker compose ps와 "
            ".env의 URI·계정·비밀번호·DB 이름을 확인하세요. "
            "자세한 점검: docs/04_TROUBLESHOOTING.md"
        ) from exc


def run(tx, statement, **parameters):
    """Always bind user input as parameters, never interpolate Cypher."""
    return tx.run(statement, parameters).data()


def read(session, callback):
    return session.execute_read(unit_of_work(timeout=10.0)(callback))


def write(session, callback):
    return session.execute_write(unit_of_work(timeout=10.0)(callback))


def check_connection():
    with graph_session() as session:
        return read(session, lambda tx: run(tx, "RETURN 1 AS connected"))[0]
