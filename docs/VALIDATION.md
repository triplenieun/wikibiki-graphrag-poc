# 실행 검증 기록

최근 검증일: **2026-10-19 (Asia/Seoul)**. 아래 기존 게시·clone 기록은 2026-10-18의 결과입니다.

저장소: [triplenieun/wikibiki-graphrag-poc](https://github.com/triplenieun/wikibiki-graphrag-poc).

## Python 3.10.12·파일 반입 검증 (2026-10-19)

사내 Python 버전이 3.10.12로 확인되어 실행 기준과 오프라인 문서를 갱신했습니다.
기존 Django·Neo4j 드라이버 등의 버전은 유지하고, Python 3.10에서 asgiref가 요구하는
`typing_extensions==4.15.0`을 고정 목록에 추가했습니다. 새 Python을 사용하는 준비 PC에서도
반입용 wheel을 빠뜨리지 않도록 이 항목에는 Python 버전 조건을 붙이지 않았습니다.

- 공식 `python:3.10.12-slim-bookworm`의 **정확한 Python 3.10.12**로 실행했습니다.
- Windows의 Python 3.14 준비 환경에서 대상 Python·플랫폼을 지정해 wheel **8개**를 받았습니다.
- 네트워크가 없는 컨테이너에서 새 가상환경을 만들고 `pip install --no-index --find-links`로 설치했습니다.
  `pip check`와 Django `check`가 통과했습니다.
- 이후 외부 연결이 차단된 별도 Docker 네트워크에 새 Neo4j를 띄워 **102개 테스트가 모두 통과**했습니다.
  이 중 실제 DB 통합 테스트는 19개이며, 기존 실습 DB는 사용하지 않았습니다.
- Windows의 Python 3.14.8에서도 별도 새 가상환경에 같은 wheel로 설치하고 `pip check`와 기본 테스트가 통과했습니다.
  이 추가 3.14 검사에서는 DB 통합 테스트 19개를 생략하고 83개를 실행했습니다.
- `neo4j:2026.09.0`의 `linux/amd64` 이미지를 `docker save`로 저장하고 `docker load`로 다시 불러왔습니다.
  이미지 태그·플랫폼이 유지되었으며 `check_neo4j`가 성공했습니다.
- 반입 자원은 Git에서 제외된 `offline/`에 준비했습니다. Neo4j tar, wheel 8개와 SHA-256 목록을 포함합니다.
  Python 검증용 컨테이너 이미지는 사내 실행에 필요하지 않습니다.
- GitHub Actions는 Python **3.10.12와 3.14** 각각에서 wheel 다운로드 후 오프라인 설치 명령과 전체 테스트를 실행하도록 바꿨습니다.

이 결과는 Linux amd64 검증 환경의 결과이며, 사내 OS·Docker 설치 상태·인증서 정책과 사내 LiteLLM 실서버 접속은
사내에서 별도로 확인해야 합니다. 과거 Python 3.14 검증 결과는 아래에 그대로 보존합니다.

## GitHub 게시·새 clone 재현 검증

완료된 작업을 다음 순서로 나눠 `main`에 올렸습니다. 각 커밋을 별도 폴더로 내보내
Django 시스템 검사와 그 시점의 기본 테스트가 통과하는 것도 확인했습니다.

| 커밋 | 작업 범위 |
|---|---|
| [`e5fc6d0`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/e5fc6d0) | Python 3.14·Django·Neo4j 실행 환경, 의존성·Git 제외 규칙 |
| [`ac8ea40`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/ac8ea40) | 서비스·팀·문서 기본 그래프, Cypher, 관리 명령·조회 API |
| [`d93a58c`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/d93a58c) | GraphRAG 검색, LiteLLM·Ollama, 그래프 화면 |
| [`458a65a`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/458a65a) | 문서 등록, 관계 추출·검토·저장 |
| [`cbc7a2f`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/cbc7a2f) | 문서 관리, 관계 철회·공유 관계 보존·검색 갱신 |
| [`9cc8d88`](https://github.com/triplenieun/wikibiki-graphrag-poc/commit/9cc8d88) | 초보자 가이드, 사용 설명서, Python·JavaScript CI |

위 코드 버전을 GitHub에서 **존재하지 않던 새 폴더**로 clone하여 다음을 확인했습니다.

1. 원래 작업 폴더의 `.env`만 복사하고 파일 해시가 동일한지 확인했습니다. `.venv`나 소스 파일을 추가로 복사하지 않았습니다.
2. clone 안에서 Python 3.14 가상환경을 새로 만들고 `pip install -r requirements.txt`, `pip check`를 통과했습니다.
3. 별도 Compose 프로젝트와 **새 빈 Neo4j 볼륨**을 사용했습니다. 기존 실습 DB와 충돌하지 않도록 검증용 포트만 `17474/17687`로 바꿨습니다. `.env`는 그대로 유지하고 검증 프로세스의 `NEO4J_URI`만 해당 포트로 지정했습니다.
4. `check`, `check_neo4j`, `seed_graph`가 성공했고 초기 그래프는 노드 11개·관계 12개였습니다.
5. 실제 DB를 포함한 Django 테스트 **102개**, JavaScript 회귀 테스트 **1개**가 모두 통과했습니다.
6. `collectstatic --noinput`으로 정적 파일 6개를 수집했습니다. 세 페이지와 JS·CSS 여섯 개가 실제 HTTP 200으로 제공됐습니다.
7. GraphRAG 근거 조회와 로컬 Qwen 모델의 실제 답변 생성을 확인했습니다. 사내 LiteLLM 실서버는 이 검증에서도 접근하지 않았습니다.
8. 실제 HTTP와 CSRF로 문서 추출 → 검토한 관계 저장 → 검색 반영 → 수정 → 삭제 → 상세 404 및 검색 제외를 확인했습니다.
9. clone의 Git 작업 트리가 깨끗하며 `.env`, `.venv`, 정적 수집 결과, 검증 파일이 추적되지 않는 것을 확인했습니다. 전체 커밋 이력에도 실제 `.env` 비밀값이 없습니다.

검증용 clone은 원래 작업 폴더의 `.test-artifacts/clone-verification/`에 보관합니다.
검증용 Django 서버와 별도 Neo4j 컨테이너·볼륨은 검증 후 정리합니다.
원래 실습용 Neo4j·Ollama와 그 데이터는 그대로 유지합니다. clone은 코드만 복제하므로
원래 DB에 등록한 문서 데이터가 새 DB로 자동 복사되지는 않습니다.

같은 PC에서 기존 환경에 연결하려면 새 clone에 `.env`를 복사한 뒤 새 가상환경에서
README 명령을 실행하면 됩니다. 원래 Compose 프로젝트가 실행 중이면 동일한 DB를
공유하므로 별도 DB 검증과 혼동하지 마세요.

GitHub Actions도 Ubuntu·Python 3.14·독립 Neo4j에서 성공했습니다.
[최초 게시 CI 실행](https://github.com/triplenieun/wikibiki-graphrag-poc/actions/runs/39134932988)에서
Python 테스트와 Node.js 24의 JavaScript 검사까지 확인했습니다.
이후 검증 기록만 추가하는 커밋은 앱 코드와 의존성을 변경하지 않습니다.

## 검증 환경

| 구성요소 | 실제 사용 버전 |
|---|---|
| 호스트 | Windows, x64 |
| Python | 3.14.8 |
| Django | 5.2.18 |
| Neo4j Python driver | 6.4.1 |
| python-dotenv | 1.2.4 |
| Neo4j Community | Docker `neo4j:2026.09.0` |
| 컨테이너 엔진 | Docker Desktop의 Linux 엔진 |
| 로컬 검증용 LLM | Ollama `0.40.6`, `qwen3.5:4b` |
| 로컬 GPU | NVIDIA GeForce RTX 4070 Laptop GPU, 8GB VRAM |

패키지의 전체 고정 버전은 [requirements.txt](../requirements.txt)에 있습니다.

## 완료한 검증

| 항목 | 결과 |
|---|---|
| Python 가상환경 의존성 설치 | 성공 |
| `python -m pip check` | 의존성 충돌 없음 |
| `python manage.py check` | Django 문제 없음 |
| Python 소스 컴파일 검사 | 성공 |
| `docker compose up -d --wait --wait-timeout 180` | 컨테이너 healthy |
| `python manage.py check_neo4j` | 실제 Bolt 연결 및 `RETURN 1` 성공 |
| `python manage.py seed_graph` | 팀 3개, 서비스 4개, 문서 4개 적재 |
| 전체 테스트 (`NEO4J_INTEGRATION=1`) | **102개 통과, 생략 없음** |
| `node --test tests/test_graphrag_freshness.mjs` | 오래된 응답 폐기·최신 근거 재조회 테스트 1개 통과 |
| 예제 반복 적재 | 노드 11개, 관계 12개 유지 |
| `graph_query services` | 담당팀을 포함한 서비스 4개 |
| `graph_query impact --service-id auth-service` | 알림·주문·결제 3개, 최소 홉 1 |
| Cypher 파일 및 주석 처리된 연습 답안 | **18개 문장 실제 실행 성공** |
| 실제 Django HTTP API | 아래 항목 모두 정상 |
| 로컬 wheel을 이용한 새 가상환경 설치 | `--no-index --find-links` 설치 성공 |
| 위 새 가상환경의 `pip check`, Django `check` | 모두 성공 |

테스트는 잘못된 참조/문서 경로, 필수 인자 누락, GET 외 메서드,
미존재 서비스 404, Neo4j 오류 503, 오류 메시지의 비밀번호 미노출도 확인합니다.
기본 `manage.py test`에서는 실제 DB 테스트 19개가 생략되고 83개가 실행됩니다.
아래 초기 예제의 노드·문서 수는 문서 등록 실습 전의 기준값입니다.

### 문서 등록·관계 검토·저장 검증

- 가상 배송 문서를 실제 로컬 Qwen 모델에 전달하여 서비스·팀과 관계 후보를 받았습니다.
- 미리보기에서 배송 서비스 설명과 문서 관계의 근거 문장을 수정하고, 잘못 추출된 문서→팀 관계를 제외했습니다.
- 검토 확인 후 브라우저에서 저장하여 `배송 서비스`, `물류팀`, 가상 문서 1개와 선택한 관계 4개를 생성했습니다.
- Neo4j의 근거 기록 4개에서 수정한 문장이 보존되고 제외한 관계가 없는 것을 확인했습니다.
- 저장 완료 링크를 누르면 GraphRAG가 배송 서비스를 선택하고 근거를 자동 조회했습니다. 신규 문서와 주문 가이드가 중복 없이 문서 2개로 표시됐습니다.
- 이어서 실제 답변을 생성하여 배송 서비스 담당팀이 물류팀이라는 사실과 신규 문서 `[D1]` 인용을 확인했습니다. 이 PC에서 생성 시간은 약 5.7초였습니다.
- 여러 서비스에 연결된 문서를 출처 하나로 합치면서 그래프의 모든 `DESCRIBES` 연결을 보존하는 통합 테스트를 추가했습니다.
- 동일 초안 재저장, 기존 담당팀 충돌, 기존 노드 속성 보존, 저장 중 오류 시 전체 롤백, 서명 변조·만료, CSRF·요청 크기·잘못된 근거 차단을 확인했습니다.

이 가상 배송 예제는 로컬 DB에 남겨두었습니다. 화면에 표시되는 서비스·팀·문서는 총 14개,
관계는 16개입니다. 별도로 관계 출처를 담은 `Assertion` 4개와 저장 잠금 노드 1개가 있습니다.
단위·통합 테스트가 생성한 UUID 기반 임시 데이터는 해당 테스트가 정리합니다.

모델이 관계 방향이나 근거를 잘못 추출한 경우도 실제로 관찰했습니다. 수정 가능한 후보는
미리보기에 경고와 함께 표시되며, 저장할 때 선택된 관계를 다시 엄격하게 검사합니다.
사내 LiteLLM 요청 형식은 단위 테스트로 확인했으며 실제 사내 서버 접속은 검증 범위 밖입니다.
UI 검증 서버는 다른 실행과 충돌하지 않도록 임시 포트 `18000`을 사용했습니다.

### 문서 관리·수정·삭제 검증

- `/documents/manage/`에서 문서 목록, 제목 검색, 원문과 관계 상세, 예제 읽기 전용 표시를 브라우저에서 확인했습니다.
- 검증용 가상 문서를 만들고 편집 화면에서 의존 대상을 주문 서비스에서 결제 서비스로 바꿨습니다. 실제 로컬 Qwen으로 재추출한 뒤 잘못된 문서→팀 제안을 제외하고 저장했습니다.
- 별도 GraphRAG 탭에서 의존 관계가 결제 서비스로 바뀌고 수정 제목이 출처에 표시되는 것을 확인했습니다. 사용자가 다시 검색 버튼을 누르지 않아도 최신 근거를 조회했습니다.
- 삭제 확인 창의 검토 체크 전후 버튼 상태를 확인했습니다. 별도로 CSRF를 적용한 실제 HTTP 삭제 API를 호출해 성공 응답, 상세 404, 삭제 후 근거 문서 0개·관계 0개를 검증했습니다.
- 테스트 문서·서비스·팀·삭제 기록은 검증 후 정리했습니다. 기존 가상 배송 문서와 기본 예제는 유지합니다.
- 공유 관계의 마지막 근거 철회, 기존·수동 관계 보존, 담당팀 변경 충돌, 버전 충돌, 동일 요청 재시도, 중간 실패 롤백, 오래된 등록 토큰의 삭제 문서 재생성 차단을 실제 DB에서 확인했습니다.
- 문서에서 생성한 노드 설명이 수정·삭제 후 독립된 LLM 근거로 남지 않는 것을 context·impact 조회 테스트로 검증했습니다.
- JavaScript 회귀 테스트는 답변 생성 중 문서가 바뀔 때 오래된 응답을 표시하지 않고, LLM을 재호출하지 않은 채 최신 근거를 조회하는지 확인합니다.
- 관리·등록 화면 JS 문법 검사와 Django 시스템 검사를 통과했습니다.

이전 실습에서 생성 경로를 확인한 배송 서비스의 두 관계에 관리 표시를 보완했습니다.
배송 서비스 설명에도 문서 출처를 표시했습니다. 생성 경로를 알 수 없는 관계를 일괄 변경하지 않았습니다.

### GraphRAG 추가 검증

사내 사용 제공자는 **LiteLLM**입니다. 여기서는 사내 서버에 접근할 수 없어
실제 생성 검증에 로컬 Ollama를 사용했고, LiteLLM 요청 형식은 단위 테스트로 확인했습니다.

| 항목 | 결과 |
|---|---|
| `/graphrag/` HTML·CSS·JavaScript | HTTP 제공 및 브라우저 표시 성공 |
| `/api/graphrag/status/` | 실제 Neo4j와 설치된 Ollama 모델 모두 연결됨 |
| `/api/graph/` | 실제 DB의 노드 11개, 관계 12개 |
| 주문 서비스 근거 조회 | 문서 3개, 노드 9개, 관계 8개, 실제 Cypher 기록 4개 |
| 인증 서비스 영향 조회 | 문서 4개, 노드 11개, 관계 12개 |
| 주문 서비스 실제 답변 생성 | 커머스팀과 관련 문서 응답, 약 9.3초, `[G]`·`[D2]` 인용 |
| 브라우저에서 인증 장애 영향 질문 | 주문·결제·알림 서비스 답변, 원문·그래프·조회 기록 표시. 최종 프롬프트로 생성 3.3초, `[G]`·`[D1]`~`[D4]` 인용 |
| LiteLLM 어댑터 단위 테스트 | `/models`, `/chat/completions`, 배포 별칭, Bearer 인증, 출력 제한, 오류 처리 확인 |
| 요청 경계 | CSRF, JSON·길이·서비스 선택 검증, 서버에서 근거 재조회 확인. 실제 모호한 질문 HTTP 400 확인 |
| LLM 오류 | 가짜 답변 없이 오류와 조회한 근거 유지 |
| 출처 검사 | 없는 문서 ID 거부, 인용 생략 시 화면에 안내 |

응답 시간은 이 PC에서 관찰한 값이며 성능 보장이 아닙니다. 모델이 인용을 생략한
응답도 실제로 발생했고 화면의 안내를 확인했습니다. 인용 ID 검사는 답변 내용의
의미적 정확성을 보장하지 않습니다. 화면에 표시되는 그래프 사실과 문서 원문을 대조해야 합니다.
최종 프롬프트 변경 후 LLM 관련 단위 테스트 14개와 Django 시스템 검사를 다시 통과했습니다.

### 실제 HTTP 확인

임시 개발 서버를 `127.0.0.1:18000`에서 실행하고 다음 응답을 확인한 뒤 종료했습니다.
사용자 실습용 README는 기본 포트 `8000`을 사용합니다.

- `/api/services/`: HTTP 200, 서비스 4개
- `/api/services/order-service/context/`: HTTP 200, 자체/의존 서비스의 문서 3개
- `/api/services/auth-service/impact/`: HTTP 200, 영향 후보 3개
- `/api/services/missing/context/`: HTTP 404, JSON 오류 응답

### Cypher 확인

`queries/00_constraints.cypher`부터 `04_impact.cypher`까지 13개 문장과
`05_practice.cypher`의 실행 가능한 답안 5개를 공식 드라이버로 실행했습니다.
담당팀 조회 4행, 주문 문맥 3행, 인증 영향 후보 3행, 주문→인증 경로 2개 등을 확인했습니다.
Browser 화면을 수동 조작하는 과정 자체는 자동화 검증하지 않았습니다.

## 검증 범위 밖

- 실제 회사 내부망·사내 서버·프록시·사내 Django 프로젝트와의 연동
- Docker 이미지 tar의 다른 PC 반입 및 `docker load` 과정
- 물리적으로 네트워크가 차단된 PC에서의 전체 설치
- macOS 호스트에서의 Python 실행과 Linux 데스크톱에서의 수동 브라우저 실습
- 실제 사내 LiteLLM 서버의 네트워크·인증·배포 모델 호환성
- 운영 부하, 백업/복구, 사용자 인증·문서별 접근 권한

로컬 wheel 설치 검증은 패키지 인덱스를 사용하지 않았다는 의미이며,
회사 반입 승인이나 모든 운영 환경 호환성을 검증했다는 의미는 아닙니다.

## 이 작업 폴더의 준비 상태

프로젝트 전용 `.venv`와 로컬 `.env`를 생성했습니다. `.env`의 DB 비밀번호는
임의 생성했으며 문서나 저장소에 기록하지 않았습니다. 이미 존재하는 `.env`를
예제 값으로 덮어쓰지 말고 본인 편집기에서 확인하세요.
Neo4j 컨테이너에 예제 데이터를 적재했고, 선택 실습용 Ollama 컨테이너와 모델도 준비했습니다.
Django 임시 검증 서버는 종료했습니다. 사용하려면 다음 명령을 실행한 뒤
`http://127.0.0.1:8000/graphrag/`를 여세요.

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`.venv`, `.env`, `.test-artifacts` 등 로컬 실행/검증 자원은 `.gitignore`에 포함되어 있습니다.
다른 PC에서는 README의 최초 설치부터 진행해야 합니다.

## 재검증 명령

프로젝트 루트의 PowerShell에서, 실습용 Neo4j가 준비된 상태로 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check_neo4j
$env:NEO4J_INTEGRATION = "1"
.\.venv\Scripts\python.exe manage.py test
Remove-Item Env:NEO4J_INTEGRATION
node --test tests/test_graphrag_freshness.mjs
```

통합 테스트는 설정된 DB에 예제 데이터를 적재합니다. 회사 운영 DB를 대상으로 실행하지 마세요.
