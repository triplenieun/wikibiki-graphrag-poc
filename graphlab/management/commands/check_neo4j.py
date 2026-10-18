from django.core.management.base import BaseCommand, CommandError

from graphlab.db import GraphConnectionError, check_connection


class Command(BaseCommand):
    help = "Neo4j 접속 및 설정한 데이터베이스에서 읽기가 가능한지 확인합니다."

    def handle(self, *args, **options):
        try:
            check_connection()
        except GraphConnectionError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Neo4j 연결 성공 (RETURN 1 확인)."))
