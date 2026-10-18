from django.core.management.base import BaseCommand, CommandError

from graphlab.db import GraphConnectionError
from graphlab.seed import seed_graph


class Command(BaseCommand):
    help = "가상의 서비스·팀·문서를 MERGE로 적재합니다. 같은 예제의 재실행은 중복되지 않습니다."

    def handle(self, *args, **options):
        try:
            counts = seed_graph()
        except (GraphConnectionError, ValueError, KeyError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"예제 적재 완료: 팀 {counts['teams']}, 서비스 {counts['services']}, "
            f"문서 {counts['documents']}, 의존 관계 {counts['dependencies']}."
        ))
        self.stdout.write("동일 예제 재실행 시 중복 생성하지 않습니다. 기존 관계를 삭제하거나 동기화하지 않습니다.")
