import json

from django.core.management.base import BaseCommand, CommandError

from graphlab import repository
from graphlab.db import GraphConnectionError


class Command(BaseCommand):
    help = "services / context / impact 예제 조회를 실행합니다."

    def add_arguments(self, parser):
        parser.add_argument("query", choices=["services", "context", "impact"])
        parser.add_argument("--service-id", help="예: order-service 또는 auth-service")

    def handle(self, *args, **options):
        name, service_id = options["query"], options["service_id"]
        if name != "services" and not service_id:
            raise CommandError("context와 impact에는 --service-id가 필요합니다.")
        try:
            if name == "services":
                result = {"services": repository.list_services()}
            elif name == "context":
                result = repository.service_context(service_id)
            else:
                result = repository.service_impact(service_id)
        except GraphConnectionError as exc:
            raise CommandError(str(exc)) from exc
        if result is None:
            raise CommandError(f"서비스를 찾을 수 없습니다: {service_id}")
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
