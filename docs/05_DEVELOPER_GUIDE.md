# 개발자를 위한 코드 안내

## 먼저 읽을 코드

| 파일 | 역할 |
|---|---|
| `config/settings.py` | `.env` 읽기, Django·Neo4j·LLM 설정 |
| `config/urls.py` | HTTP 주소와 view 연결 |
| `graphlab/views.py` | GET 요청을 받아 JSON으로 반환, 404/503 처리 |
| `graphlab/repository.py` | 서비스 목록·문맥·영향 후보를 찾는 Cypher |
| `graphlab/graphrag.py` | 서비스 식별, 실제 그래프 근거·원문·실행 Cypher 수집 |
| `graphlab/llm.py` | Ollama / 사내 LiteLLM 연결 및 출처가 포함된 답변 요청 |
| `graphlab/rag_views.py` | GraphRAG 페이지·상태·검색·생성 HTTP API |
| `graphlab/ingestion.py` | 문서 관계 추출·검증, 미리보기 서명, Neo4j 저장 |
| `graphlab/document_management.py` | 문서 목록·상세, 버전 충돌 확인, 관계 교체·철회와 삭제 |
| `graphlab/ingestion_views.py` | 문서 등록·관리 페이지와 목록·상세·추출·저장·수정·삭제 HTTP API |
| `graphlab/templates/graphlab/`, `graphlab/static/graphlab/` | CDN 없는 HTML/CSS/JavaScript 화면 |
| `graphlab/db.py` | Neo4j 공식 드라이버 연결, 세션/트랜잭션 수명 관리 |
| `graphlab/seed.py` | 샘플 검증, 제약조건 생성, 데이터 적재 |
| `graphlab/management/commands/` | Django `manage.py` 명령 |
| `data/sample_graph.json` | 직접 고쳐 볼 수 있는 가상 업무 데이터 |
| `docs/samples/` | 문서 노드의 원문 |
| `queries/` | Neo4j Browser에서 실행할 학습용 Cypher |
| `tests/` | DB 없이 실행하는 테스트와 선택적 실제 DB 테스트 |

기본 조회 API는 URL → view → repository → Neo4j 드라이버 순서로 처리됩니다.
CLI의 `graph_query`도 동일한 repository 함수를 사용합니다.
GraphRAG 요청은 URL → `rag_views` → `graphrag.retrieve()` → Neo4j 드라이버로 근거를 수집하고,
답변 생성 요청이면 `llm.generate_answer()`로 선택한 LLM을 호출합니다.
문서 등록 요청은 `ingestion_views` → `ingestion`에서 추출 미리보기를 만들고,
별도의 저장 요청에서 사용자 검토 결과를 검증하여 Neo4j에 기록합니다.
문서 관리에서는 저장한 원문과 문서별 관계 근거를 읽어 검토 화면을 구성하고,
수정·삭제 요청의 버전을 확인한 뒤 문서와 관계를 하나의 트랜잭션으로 변경합니다.

## Django ORM과의 관계

이 프로젝트는 Neo4j를 Django ORM의 `DATABASES`에 등록하지 않습니다.
`DATABASES = {}`이며 관계형 모델, 인증, 세션, admin은 설치하지 않았습니다.
따라서 `migrate`나 `createsuperuser`는 이 실습의 준비 단계가 아닙니다.

실제 회사 Django 프로젝트에서는 기존 PostgreSQL 등 관계형 DB 설정을 유지하고,
Neo4j 접속 코드와 설정을 별도로 추가할 수 있습니다. Django ORM 모델을 Neo4j가
자동으로 이해하거나 마이그레이션하는 것은 아닙니다.

## 연결과 트랜잭션

예제는 한 작업마다 드라이버와 세션을 열고 `with` 블록에서 닫습니다.
연결 수명을 쉽게 추적하기 위한 작은 실습용 구성입니다. 요청량이 많은 환경에서는
프로세스별 드라이버 재사용과 종료 처리를 설계하고 세션은 작업마다 생성합니다.

조회는 `execute_read`, 데이터 적재는 `execute_write`를 사용합니다.
관리 트랜잭션은 재시도될 수 있으므로 콜백 안에서 이메일 전송 같은 외부 부수 효과를
실행하지 않습니다. 데이터 적재는 같은 입력을 다시 실행해도 중복되지 않는 `MERGE`를 사용합니다.
제약조건 생성은 데이터 적재 트랜잭션과 분리됩니다.

`context` 조회의 서비스·의존성·문서 검색은 한 관리 트랜잭션 안에서 실행합니다.
이것을 운영 중 모든 변경에 대한 스냅샷 일관성 보장으로 해석하지는 않습니다.
운영 환경의 동시 갱신 정책은 별도로 정해야 합니다.

문서 등록·수정·삭제 요청끼리는 공용 잠금 노드의 갱신으로 직렬화하고, 문서 버전으로
오래된 초안을 거부합니다. Neo4j Browser나 별도 프로그램의 임의 쓰기까지 이 잠금에
참여하는 것은 아니므로, 운영 환경에서는 그래프 쓰기 경로를 함께 관리해야 합니다.

## 사용자 입력과 오류 응답

서비스 ID는 Cypher 문자열에 붙이지 않고 `$service_id` 매개변수로 전달합니다.
라벨, 관계 유형, 탐색 깊이는 코드에 정의되어 있고 임의 Cypher 실행 API는 제공하지 않습니다.

기본 서비스 조회 API의 응답은 다음과 같습니다.

| 상황 | HTTP 결과 |
|---|---|
| 정상 조회 | 200 + JSON |
| 알려지지 않은 서비스 ID | 404 + `error` |
| Neo4j 연결/질의 실패 | 503 + 점검 안내 |
| GET 이외 메서드 | 405 |

GraphRAG의 근거 조회·답변 생성 API는 JSON 본문을 받는 POST이며 CSRF 토큰이 필요합니다.
잘못된 입력이나 식별할 수 없는 서비스는 `400`, DB 또는 LLM 연결 실패는 `503`을 반환합니다.
LLM 생성만 실패하면 확보한 검색 근거도 함께 반환합니다. 경로와 요청 형식은
[GraphRAG API 안내](07_GRAPHRAG_GUIDE.md#6-개발자가-사용할-http-api)를 참고하세요.

문서 등록 API도 JSON POST와 CSRF 보호를 사용합니다. 추출 요청은 DB에 쓰지 않고
원문을 서명한 `review_token`과 관계 후보를 반환합니다. 저장 요청의 노드·관계·근거를
다시 검증한 후 하나의 트랜잭션에서 저장합니다. 기존 노드의 속성은 유지하고,
다른 담당팀과의 충돌은 `409`로 반환합니다. 임의 Cypher는 받지 않습니다.
입력 형식과 만료·재시도 규칙은 [문서 등록 가이드](08_DOCUMENT_INGESTION.md)를 참고하세요.

문서 관리 API는 목록·상세 GET과 재추출·수정·삭제 POST를 제공합니다. 수정 시
서명된 미리보기가 가리키는 원본 버전을, 삭제 시 요청의 `version`을 현재 DB와 비교합니다.
다른 요청이 먼저 변경한 경우 `409`를 반환하므로 최신 상세를 다시 불러와 검토해야 합니다.
없는 문서는 `404`이며 예제로 적재한 읽기 전용 문서는 관리 화면에서 변경할 수 없습니다.
요청 형식은 [문서 관리 API](09_DOCUMENT_MANAGEMENT.md#7-개발자를-위한-api)를 참고하세요.

사용자 응답에는 드라이버 예외 원문이나 비밀번호를 포함하지 않습니다.
실습은 로컬 접근을 전제로 하며 사용자 로그인·문서별 접근 권한·운영용 감사 로그는 포함하지 않습니다.
사내 운영 API로 확장할 때는 기존 인증 체계와 데이터 권한 필터를 검색 단계에 적용합니다.

## 예제 데이터를 바꾸는 방법

1. `data/sample_graph.json`에 고유한 ID를 가진 팀 또는 서비스를 추가합니다.
2. 문서는 `docs/samples/`에 UTF-8 Markdown으로 저장하고 JSON의 `source`에 상대 경로를 적습니다.
3. `owner_id`, `service_id`, `source_id`, `target_id`는 실제 존재하는 ID를 가리켜야 합니다.
4. `seed_graph`를 다시 실행하고 서비스·문서 조회 결과를 확인합니다.

문서의 `body`는 적재할 때 파일을 읽어 Neo4j에 저장한 문자열입니다.
`source`는 출처 경로이며, 조회할 때 DB가 로컬 파일을 자동으로 읽는 것은 아닙니다.
원문을 수정했다면 다시 적재해야 DB의 내용도 바뀝니다.

현재 seed는 예제를 추가·갱신하는 도구입니다. **입력에서 사라진 노드/관계를 삭제하지 않습니다.**
예를 들어 서비스 담당팀을 바꾸고 재적재하면 기존 `OWNED_BY`도 남습니다.
완전한 동기화가 필요하다면 삭제 범위, 출처, 변경 이력, 권한을 명시한 별도 적재 절차를 설계해야 합니다.
수정 실습에는 이 프로젝트 전용 DB를 사용하세요.

## 문서에서 관계를 추가하는 방법

`/documents/`에서 문서를 입력하면 선택한 LLM이 구조화된 노드·관계 후보를 만듭니다.
추출 결과를 바로 DB에 쓰지 않고, 사용자가 기존 노드와의 연결·방향·근거 문장을 확인합니다.
저장 시 `Document`의 본문과 `DESCRIBES`, `DEPENDS_ON`, `OWNED_BY` 관계를 기록하고,
문서별 관계 근거는 `Assertion` 노드로 보관합니다. 같은 관계를 여러 문서가 뒷받침할 수 있습니다.

미리보기 토큰은 1시간 유효하며 `DJANGO_SECRET_KEY`로 서명합니다. 운영하는 Django
프로세스 간에는 동일한 비공개 키를 설정해야 합니다. 기본 임시 키는 서버를 재시작하면
바뀌므로 이전 미리보기가 무효화됩니다. 토큰은 변조 검사용이며 원문 암호화 기능은 아닙니다.

저장한 문서와 관계는 기존 업무 그래프의 라벨·관계 유형을 사용하므로 다음 GraphRAG
요청부터 조회됩니다. 검색 인덱스 재구축은 필요하지 않습니다. 문서 수정·삭제도 같은
조회 경로에 바로 반영됩니다. 이미 생성한 답변은 과거 근거에 대한 결과이므로 최신
근거를 조회한 후 다시 생성해야 합니다.

## 등록한 문서를 수정·삭제하는 방법

`/documents/manage/`에서 등록 문서를 선택합니다. 제목·본문·출처를 바꿨다면 관계를
다시 추출하고 검토하여 저장합니다. 원문이 같으면 저장된 관계만 수정하여 검토할 수도
있습니다. 문서 ID는 유지하며 이전 `Assertion`을 새 검토 결과로 교체합니다.
관계 교체 중 오류가 발생하면 원문과 이전 관계 근거를 함께 되돌립니다.

앱이 새로 만든 관계에는 `managed_by_documents=true`를 기록합니다. 문서의 근거를
철회할 때 같은 관계를 뒷받침하는 다른 `Assertion`이 없고 앱이 관리하는 관계일 때만
삭제합니다. `DESCRIBES`는 삭제하는 문서에 속한 연결이므로 함께 제거합니다.
기존 예제·수동 관계와 생성 경로를 알 수 없는 이전 버전의 관계는 보존합니다.
서비스·팀 노드는 다른 문서가 재사용할 수 있으므로 이름·설명과 함께 유지합니다.
따라서 문서 수정 화면은 기존 서비스·팀의 기본 정보를 편집하는 화면이 아닙니다.

문서 삭제 후에는 원문과 문서별 `Assertion`을 제거하고 `DocumentTombstone`에 삭제한
ID·버전·시각을 남깁니다. 이 기록은 오래된 미리보기 요청이 삭제한 문서를 되살리는 것을
막기 위한 것이며 원문 백업이나 복원 기능이 아닙니다. 삭제 기록과 근거 기록은
GraphRAG의 업무 그래프 화면에 표시하지 않습니다.

예제 문서는 목록에서 확인할 수 있지만 읽기 전용입니다. 예제 원문 변경은
`docs/samples/` 수정과 `seed_graph` 재실행으로 처리합니다. 문서 등록 기능과 달리
seed는 원본에서 사라진 관계를 정리하지 않는다는 점을 구분하세요.
상세한 사용자 절차와 공유 관계 예시는 [문서 관리 가이드](09_DOCUMENT_MANAGEMENT.md)를 참고하세요.

## GraphRAG로 확장할 지점

`service_context()`는 질문에 필요한 근거를 구조적으로 모으는 작은 시작점입니다.
추가한 `graphrag.retrieve()`는 같은 업무 모델을 사용해 질문의 서비스를 식별하고
담당팀·문서를 연결하여 실제 실행 Cypher와 함께 반환합니다. `llm.generate_answer()`가
이를 사내 LiteLLM에 전달하며, 개인 검증 환경에서는 Ollama를 선택할 수 있습니다. 자세한 설정은 [GraphRAG 가이드](07_GRAPHRAG_GUIDE.md)를 참고하세요.
서비스 식별은 이름 규칙과 선택 입력이며 임베딩·벡터 검색은 없습니다.
다음 기능을 추가해 확장할 수 있습니다.

- 문서를 청크로 나누고 원문·청크·서비스를 연결하기
- 사내 임베딩 모델로 의미 검색하기
- 현재 문서 단위 근거를 청크 단위 근거로 발전시키기
- 현재 답변의 출처 표기를 평가용 질문·정답과 대조해 정확성 검증하기

## 테스트

Windows PowerShell, 프로젝트 루트에서:

```powershell
.\.venv\Scripts\python.exe manage.py test
```

기본 테스트는 실제 Neo4j에 접속하지 않습니다. DB가 있는 경우 실습 전용 DB인지 확인한 다음:

```powershell
$env:NEO4J_INTEGRATION = "1"
.\.venv\Scripts\python.exe manage.py test
Remove-Item Env:NEO4J_INTEGRATION
```

통합 테스트는 `.env`가 지정한 DB를 사용하며 Django가 임시 Neo4j 테스트 DB를 자동으로
생성하지 않습니다. 기본 조회 테스트는 가상 예제를 두 번 적재하여 중복 방지와 조회 결과를 검증합니다.
문서 등록 통합 테스트는 `it-`와 UUID로 구분한 자체 문서·서비스·팀을 만들고,
저장 직후 검색, 동일 요청 재시도, 담당팀 충돌, 트랜잭션 되돌리기, 기존 속성 보존을 확인합니다.
종료 시에는 해당 테스트가 만든 ID와 그 문서의 `Assertion`만 `DETACH DELETE`로 정리합니다.
문서 관리 통합 테스트는 같은 관계를 여러 문서가 뒷받침하는 경우, 문서 개정과
삭제의 검색 반영, 기존 관계 보존, 오래된 버전의 충돌과 재시도를 검증합니다.
기존 예제 데이터나 전체 DB를 삭제하지 않으며 공용 제약조건·저장 잠금 노드는 유지합니다.
초기 예제는 노드 11개·관계 12개이지만, 문서 등록 후 전체 DB 수치는 달라집니다.

GraphRAG가 문서 변경 후 오래된 답변과 근거를 비우고 검색을 갱신하는 흐름은 Node.js가
설치된 환경에서 별도로 확인할 수 있습니다. 앱 실행에 Node.js가 필요한 것은 아닙니다.

```powershell
node --test tests/test_graphrag_freshness.mjs
```

GitHub Actions 설정은 `.github/workflows/tests.yml`에 있습니다.
독립된 Neo4j 서비스와 Python 3.10.12·3.14 매트릭스로 같은 테스트를 실행하고, Node.js 24로 화면 갱신 회귀 테스트와 JavaScript 문법을 검사합니다.
현재 로컬 검증 결과는 [VALIDATION.md](VALIDATION.md)를 확인하세요.

## 버전 갱신

`requirements.txt`는 직접·간접 의존성을 고정합니다. `requirements.in`은 직접 의존성의 허용 범위입니다.
일상 설치는 `requirements.txt`를 사용하고, 버전 갱신은 별도 가상환경에서 의도적으로 수행합니다.
사내 기준은 Python 3.10.12이며 3.14 개발 환경도 지원합니다. 새 코드와 의존성을 추가할 때 두 버전에서 확인하고, 3.11 이상에서만 제공하는 표준 라이브러리나 문법에 무심코 의존하지 않도록 합니다. 사내 반입용 wheel은 대상 Python·OS·CPU 아키텍처에 맞춰 준비하며 개발 PC의 가상환경을 복사하지 않습니다.
회사 Django 버전이 다르면 공식 Python 호환성 표를 확인하고 의존성 및 테스트를 함께 갱신하세요.

참고: [Django Python 호환성](https://docs.djangoproject.com/en/5.2/faq/install/#what-python-version-can-i-use-with-django),
[Neo4j Python 드라이버](https://neo4j.com/docs/python-manual/current/),
[Neo4j 트랜잭션](https://neo4j.com/docs/python-manual/current/transactions/).
