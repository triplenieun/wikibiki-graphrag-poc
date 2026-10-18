# Neo4j 첫 실습: 서비스·팀·문서 연결하기

Python 3.14와 Django를 사용해 **서비스 → 의존 서비스 → 담당팀 → 운영 문서**를 조회하는 실습 프로젝트입니다. 기본 그래프 실습은 AI 없이 실행할 수 있고, GraphRAG 페이지는 조회한 근거를 사내 LiteLLM 서버에 전달해 답변을 생성합니다. 개인 PC에서 검증할 때는 로컬 Ollama를 선택할 수 있습니다.

실습을 마치면 다음을 할 수 있습니다.

- 노드·관계·속성의 차이를 설명합니다.
- Neo4j에 예제 데이터를 넣고, Cypher로 관계를 따라 조회합니다.
- 같은 조회를 Django 관리 명령과 HTTP API에서 실행합니다.
- 문서에서 추출한 관계를 확인·수정하고 Neo4j에 저장합니다.
- 등록한 문서를 목록에서 찾아 수정·삭제하고 검색 결과의 변화를 확인합니다.
- 내부망으로 코드와 실행 자원을 옮길 준비를 합니다.

GraphRAG 페이지에서 질문, 검색된 그래프, 실행한 Cypher, 원문 출처, LLM 답변을 함께 확인합니다. 문서 등록 페이지에서는 LLM이 추출한 관계를 미리보기로 검토한 뒤 저장할 수 있습니다. 문서 관리 페이지에서는 등록 문서를 수정·삭제합니다. 변경한 문서와 관계는 다음 GraphRAG 조회에 반영됩니다. 검색은 서비스 그래프의 관계를 따라 근거를 모으며, 임베딩·벡터 검색은 포함하지 않습니다.

## GraphRAG 페이지부터 사용하기

아래 본문의 DB 준비·예제 적재를 완료한 뒤 Django를 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

[http://127.0.0.1:8000/graphrag/](http://127.0.0.1:8000/graphrag/)를 엽니다.
**근거만 조회**는 LLM 없이 동작합니다. **답변 생성**은 `.env`에서 선택한 LLM 서버를 사용합니다.

사내 LiteLLM 서버를 사용할 때는 `.env`의 다음 항목을 사내에서 설정하세요.
아래 주소와 모델명은 실제 접속 정보가 아닌 예시입니다. 기존 Neo4j 설정은 유지합니다.

```dotenv
LLM_PROVIDER=litellm
LITELLM_BASE_URL=http://YOUR_INTERNAL_LITELLM_HOST:4000/v1
LITELLM_MODEL=YOUR_DEPLOYED_MODEL_ALIAS
LITELLM_API_KEY=YOUR_APPLICATION_KEY
```

서버에서 인증을 요구하지 않는 경우에만 키를 비워 둡니다. `/v1` 포함 여부는 사내 게이트웨이 설정에 맞추며,
주소 끝에 `/chat/completions`를 붙이지 않습니다. 설정 후 Django를 재시작하세요.
현재 회사 서버에 접근할 수 없는 개발 PC에서는 [무료 로컬 LLM 안내](docs/06_FREE_LLM_OPTIONS.md)의 Ollama 경로를 선택할 수 있습니다. 사내 LiteLLM을 사용할 때는 Ollama를 설치할 필요가 없습니다.
실제 사내 서버 접속 정보나 키를 GitHub에 올리지 않습니다.

자세한 사용 흐름과 연결 방법은 [GraphRAG 사용 가이드](docs/07_GRAPHRAG_GUIDE.md)를 읽으세요.

## 문서를 추가하고 관계 만들기

[문서 등록 페이지](http://127.0.0.1:8000/documents/)에서 제목·본문을 입력하거나 UTF-8 `.txt`/`.md` 파일을 선택합니다. **관계 추출 → 노드·관계·근거 문장 확인 및 수정 → 저장** 순서로 진행합니다. 추출만으로 DB를 변경하지 않으며, 확인한 결과를 저장한 후 GraphRAG에서 조회합니다.

예를 들어 `배송 서비스는 주문 서비스에 의존하며 물류팀이 담당합니다.`라는 문서에서 배송 서비스·물류팀을 새로 만들고, 기존 주문 서비스와 연결할 수 있습니다. 처음 실행할 때의 설정과 실습은 [문서 등록 가이드](docs/08_DOCUMENT_INGESTION.md)를 참고하세요.

## 등록한 문서 관리하기

[문서 관리 페이지](http://127.0.0.1:8000/documents/manage/)에서 저장된 문서를 찾고 원문과 관계를 확인합니다. 수정할 때는 원문을 고친 뒤 **관계 다시 추출 → 미리보기 검토 → 변경 저장** 순서로 진행합니다. 삭제하면 해당 문서와 그 문서의 근거 기록이 검색에서 빠집니다.

다른 문서도 뒷받침하는 관계와 예제·수동으로 만든 관계는 보존합니다. 서비스·팀 자체도 삭제하지 않습니다. 어떤 관계가 사라지고 남는지, 충돌이 발생했을 때의 처리 방법은 [문서 관리 가이드](docs/09_DOCUMENT_MANAGEMENT.md)를 참고하세요.

## 읽는 순서

처음에는 이 README의 1~8단계를 따라 실행하세요. 이후 아래 문서를 읽으면 코드와 조회 결과를 이해하기 쉽습니다.

| 문서 | 내용 |
| --- | --- |
| [그래프 기본 개념](docs/01_GRAPH_BASICS.md) | 노드, 라벨, 속성, 관계, 홉과 예제 모델 |
| [Cypher 실습](docs/02_CYPHER_LAB.md) | 쿼리 읽는 법, 직접 조회하기, 예상 결과, 연습문제 |
| [내부망 반입·실행](docs/03_OFFLINE_SETUP.md) | 이미지·패키지 준비, 인터넷 없는 설치, GitHub/사내 Git 활용 |
| [문제 해결](docs/04_TROUBLESHOOTING.md) | Python, Docker, 연결, 비밀번호, 조회 결과 문제 |
| [Django 개발자 가이드](docs/05_DEVELOPER_GUIDE.md) | 코드 구조, API, 기존 사내 Django 프로젝트와 연결하기 |
| [무료 LLM 조사](docs/06_FREE_LLM_OPTIONS.md) | 사내 LiteLLM과 개인 실습용 로컬 모델, 무료 API 비교 |
| [GraphRAG 사용 가이드](docs/07_GRAPHRAG_GUIDE.md) | LLM 연결, 질문·근거·답변 확인, 내부망 전환 |
| [문서 등록과 관계 추출](docs/08_DOCUMENT_INGESTION.md) | 문서 입력, LLM 추출, 미리보기 수정, 저장과 검색 반영 |
| [문서 목록·수정·삭제](docs/09_DOCUMENT_MANAGEMENT.md) | 원문 개정, 관계 교체·철회, 공유 관계 보존, 동시 수정 충돌 |
| [검증 기록](docs/VALIDATION.md) | 이 작업 환경에서 실제 실행한 검증과 실행하지 못한 항목 |

## 프로젝트 구성

Neo4j는 Docker 컨테이너 안에서 실행됩니다. Django는 PC의 Python 가상환경에서 실행되며, 공식 Neo4j Python 드라이버로 DB에 연결합니다.

| 구성요소 | 역할 | 접속 위치 |
| --- | --- | --- |
| Neo4j Community | 그래프 데이터 저장·Cypher 실행 | Bolt `127.0.0.1:7687` |
| Neo4j Browser | 사람이 Cypher를 입력하고 결과를 보는 웹 도구 | [http://localhost:7474](http://localhost:7474) |
| Django | 관리 명령, 그래프 조회, GraphRAG 답변, 문서 등록·수정·삭제 제공 | [http://127.0.0.1:8000](http://127.0.0.1:8000) |

DB 포트는 로컬 PC에서만 접속하도록 설정되어 있습니다. Django도 아래 안내처럼 `127.0.0.1`에 실행합니다. 이 기본 구성은 개인 실습용입니다.

### 버전 기준

- Python **3.14**
- Django **5.2.18 LTS**: Python 3.14 지원은 5.2.8부터입니다. 이 저장소는 호환되는 패치 버전을 `requirements.txt`에 고정합니다. [Django 공식 지원 안내](https://docs.djangoproject.com/en/5.2/releases/5.2/#python-compatibility)
- Neo4j 공식 Python 드라이버 **6.4.1**: 정확한 의존성 목록은 `requirements.txt`가 기준입니다. [드라이버 설치 문서](https://neo4j.com/docs/python-manual/current/install/)
- Neo4j Community Docker 이미지 **`neo4j:2026.09.0`**: 공식 배포 태그를 고정합니다. [Neo4j Docker 안내](https://neo4j.com/docs/operations-manual/current/docker/introduction/)

회사에서 사용하는 Django 버전이 다르다면, 기존 서비스의 패키지를 바로 바꾸지 말고 별도 가상환경에서 먼저 실습하세요. **Django ORM은 이 프로젝트의 Neo4j 연결을 담당하지 않습니다.** SQLite나 PostgreSQL 테이블을 만들지 않으므로 `manage.py migrate`도 필요하지 않습니다.

## 1. 필요한 프로그램 설치하기

아래 기본 경로는 **Windows PowerShell** 기준입니다. 인터넷이 없는 PC에서는 먼저 [내부망 반입·실행](docs/03_OFFLINE_SETUP.md)을 따르세요.

1. [Python 공식 다운로드](https://www.python.org/downloads/windows/)에서 Python 3.14 일반 빌드를 설치합니다. 설치 후 PowerShell에서 `python` 명령을 사용할 수 있어야 합니다.
2. [Docker Desktop for Windows 설치 안내](https://docs.docker.com/desktop/setup/install/windows-install/)에 따라 Docker Desktop을 설치합니다. Windows에서는 WSL 2 등 안내된 실행 조건을 갖추고, **Linux 컨테이너**를 사용합니다. 설치 완료 후 Docker Desktop을 실행하세요. 회사 PC에서는 회사가 승인한 Docker 실행 환경을 사용합니다.
3. GitHub에서 내려받을 계획이라면 [Git](https://git-scm.com/downloads)도 설치합니다.

새 PowerShell 창을 열어 확인합니다.

```powershell
python --version
docker --version
docker compose version
git --version
```

첫 줄이 `Python 3.14.x`여야 합니다. `py` 런처가 설치되어 있지 않아도 `python`이 올바르게 실행되면 실습할 수 있습니다. `docker --version`은 설치 여부만 확인하므로, Docker Desktop도 실행되어 있어야 합니다.

Docker로 Neo4j를 실행하므로 PC에 Java나 Neo4j를 별도로 설치할 필요는 없습니다.

## 2. 작업 폴더에서 Python 가상환경 만들기

이미 이 폴더에서 작업 중이면 그대로 진행합니다. 다른 PC나 빈 작업 폴더에서 시작할 때는 아래 명령으로 저장소를 받습니다.

```powershell
git clone https://github.com/triplenieun/wikibiki-graphrag-poc.git
cd wikibiki-graphrag-poc
```

이후 모든 명령은 `manage.py`와 `compose.yaml`이 있는 **프로젝트 최상위 폴더**에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

가상환경은 이 프로젝트의 Python 패키지를 다른 프로젝트와 분리하는 폴더입니다. 이후 `python.exe`의 전체 상대 경로를 사용하는 이유는 **항상 이 가상환경을 사용하기 위해서**입니다. PowerShell의 활성화 스크립트나 실행 정책 변경은 필요하지 않습니다.

설치된 패키지의 의존 관계를 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m pip check
```

정상이면 `No broken requirements found.`가 출력됩니다.

### macOS/Linux에서는

Python 3.14와 Docker가 설치된 환경에서 다음을 사용합니다.

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

아래 안내의 `.\.venv\Scripts\python.exe`를 `.venv/bin/python`으로 바꾸면 됩니다. PowerShell 전용 `Copy-Item`, `Get-Content`, `Invoke-RestMethod`도 각각 파일 복사, 파일 보기, `curl` 등 해당 OS의 도구로 바꿉니다.

## 3. 접속 설정 만들기

최초 한 번만 실행합니다. 이미 `.env`가 있다면 덮어쓰지 말고 내용을 확인하세요.

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env`에서 `NEO4J_PASSWORD`를 **직접 정한 긴 비밀번호**로 변경하고 저장합니다. 처음에는 영문·숫자·하이픈·밑줄을 섞은 16자 이상의 값을 사용하면 설정 파일의 특수문자 해석 문제를 줄일 수 있습니다. 예제의 안내용 값을 그대로 사용하지 마세요.

주요 설정의 의미는 다음과 같습니다. 기본 주소와 사용자명은 이 실습에서 그대로 사용합니다.

| 설정 | 기본값 또는 작성 방법 | 의미 |
| --- | --- | --- |
| `NEO4J_URI` | `bolt://127.0.0.1:7687` | Python이 DB에 접속하는 주소 |
| `NEO4J_USERNAME` | `neo4j` | DB 사용자 이름 |
| `NEO4J_PASSWORD` | 직접 설정 | DB 비밀번호 |
| `NEO4J_DATABASE` | `neo4j` | 조회할 데이터베이스 이름 |

`.env`에는 개인 환경과 비밀번호가 들어갑니다. 저장소에는 `.env.example`만 포함하고, 실제 `.env`는 Git에 올리지 않습니다.

**비밀번호는 DB를 처음 만들 때 적용됩니다.** 이미 DB 볼륨이 있다면 `.env`만 수정해도 기존 DB 비밀번호가 바뀌지는 않습니다. 자세한 복구 절차는 [문제 해결](docs/04_TROUBLESHOOTING.md)을 보세요.

## 4. Neo4j 시작하기

```powershell
docker compose pull
docker compose up -d
docker compose ps
```

`pull`은 고정된 Neo4j 이미지를 내려받고, `up -d`는 DB를 백그라운드에서 실행합니다. 첫 다운로드와 DB 초기화에는 시간이 걸릴 수 있습니다.

아직 DB가 준비되지 않았다면 로그를 확인하세요.

```powershell
docker compose logs --tail 80 neo4j
```

이제 Django 설정과 실제 DB 연결을 각각 확인합니다.

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check_neo4j
```

`check`는 Django 설정을 확인하고, `check_neo4j`는 **실제 Neo4j 접속과 간단한 조회**를 확인합니다. DB가 시작 중이라면 잠시 후 `check_neo4j`를 다시 실행합니다. 연결 확인이 성공한 다음 단계로 진행하세요.

## 5. 예제 데이터 넣기

```powershell
.\.venv\Scripts\python.exe manage.py seed_graph
```

데이터 원본은 [data/sample_graph.json](data/sample_graph.json), 문서 원문은 [docs/samples](docs/samples)입니다. 적재 코드가 Markdown 원문을 읽어 문서 노드의 `body` 속성에도 저장합니다. 예제의 모든 노드는 `Lab` 라벨과 대상별 라벨을 함께 가집니다.

| 종류 | 개수 | 데이터 |
| --- | ---: | --- |
| `Service` | 4 | 주문, 인증, 결제, 알림 서비스 |
| `Team` | 3 | 커머스팀, 플랫폼팀, 결제팀 |
| `Document` | 4 | 각 서비스의 운영 문서 |
| 전체 노드 | **11** | `Lab` 라벨로 실습 데이터 구분 |
| 전체 관계 | **12** | `DEPENDS_ON` 4개, `OWNED_BY` 4개, `DESCRIBES` 4개 |

`seed_graph`는 고유 ID를 기준으로 `MERGE`를 사용합니다. **같은 예제 데이터를 다시 넣어도 노드와 관계가 중복 생성되지 않습니다.** 기존 실습 데이터의 속성은 예제 내용으로 갱신될 수 있습니다. 이 명령은 실습 그래프를 비우거나 원본과 완전히 동기화하는 명령은 아닙니다. 원본에서 노드·관계를 지워도 DB에서 자동 삭제되지 않으며, 담당팀을 바꿔 재적재하면 이전 팀 관계도 남습니다. 관계를 변경하는 실습에서는 이 제한을 고려하세요.

## 6. Neo4j Browser에서 그래프 보기

웹 브라우저에서 [http://localhost:7474](http://localhost:7474)를 엽니다. 연결을 요구하면 다음 정보를 입력합니다.

- 연결 주소: `bolt://localhost:7687`
- 사용자 이름: `neo4j`
- 비밀번호: `.env`에 직접 설정한 값
- 데이터베이스 선택이 있다면: `neo4j`

Browser의 쿼리 입력창에 아래 Cypher를 붙여넣고 실행합니다.

```cypher
MATCH (n:Lab)
RETURN n;
```

노드는 괄호 `( )`로 표현합니다. `MATCH`는 조건에 맞는 대상을 찾고, `RETURN`은 결과로 받을 값을 지정합니다. 결과를 **Graph** 보기로 전환하면 노드들을 볼 수 있습니다.

관계까지 명시적으로 조회하려면 다음 쿼리를 실행합니다.

```cypher
MATCH (a:Lab)-[r]->(b:Lab)
RETURN a, r, b;
```

이제 “주문 서비스가 사용하는 서비스의 담당팀”을 찾아봅니다.

```cypher
MATCH (:Lab:Service {id: 'order-service'})
      -[:DEPENDS_ON]->(dependency:Lab:Service)
      -[:OWNED_BY]->(team:Lab:Team)
RETURN dependency.name AS service_name,
       team.name AS team_name
ORDER BY dependency.id;
```

**Table** 보기에서 다음 두 행을 확인할 수 있습니다.

| service_name | team_name |
| --- | --- |
| 인증 서비스 | 플랫폼팀 |
| 결제 서비스 | 결제팀 |

더 많은 쿼리는 [queries](queries)에 있습니다. 파일 전체에 여러 쿼리가 있으면 **세미콜론으로 끝나는 쿼리 한 블록씩** 복사해 실행하세요. 파일마다 설명 주석이 있으며, [Cypher 실습](docs/02_CYPHER_LAB.md)에서 각 조회를 풀이합니다.

## 7. Python 명령과 Django API에서 조회하기

터미널에서도 같은 데이터를 조회할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe manage.py graph_query services
.\.venv\Scripts\python.exe manage.py graph_query context --service-id order-service
.\.venv\Scripts\python.exe manage.py graph_query impact --service-id auth-service
```

- `services`: 서비스 4개와 각각의 담당팀을 확인합니다.
- `context`: 주문 서비스 자체와 **직접 의존하는** 인증·결제 서비스의 팀과 문서를 확인합니다. 질문에 필요한 근거를 묶는 작은 예제입니다.
- `impact`: 인증 서비스에 의존하는 서비스를 **역방향으로 최대 5홉** 탐색합니다. 주문·결제·알림 서비스가 영향 후보입니다. 이 결과는 의존 관계로 찾은 후보이며, 실제 장애 발생을 확정하지는 않습니다.

웹 API를 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

이 터미널은 서버가 실행되는 동안 계속 열어 둡니다. 웹 브라우저에서 아래 주소를 열면 JSON 결과를 볼 수 있습니다.

| 주소 | 내용 |
| --- | --- |
| [http://127.0.0.1:8000/](http://127.0.0.1:8000/) | 사용할 수 있는 경로 안내 |
| [http://127.0.0.1:8000/api/services/](http://127.0.0.1:8000/api/services/) | 서비스 목록 |
| [http://127.0.0.1:8000/api/services/order-service/context/](http://127.0.0.1:8000/api/services/order-service/context/) | 주문 서비스의 관련 팀·문서 |
| [http://127.0.0.1:8000/api/services/auth-service/impact/](http://127.0.0.1:8000/api/services/auth-service/impact/) | 인증 서비스의 영향 후보 |

다른 PowerShell 창에서 HTTP 응답을 확인할 수도 있습니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/services/order-service/context/ | ConvertTo-Json -Depth 10
```

`context` 결과의 `service`와 `owner`는 요청한 서비스와 담당팀, `dependencies`는 직접 의존하는 서비스와 그 팀, `documents`는 세 서비스의 관련 문서입니다. 각 문서에는 `source` 원본 경로와 `body` 원문이 함께 들어갑니다. 이 API는 조회 결과를 반환하며, 자연어 답변은 [GraphRAG 페이지](http://127.0.0.1:8000/graphrag/)에서 생성합니다.

URL에 없는 서비스 ID를 넣으면 `404`, DB 연결 문제는 `503` 오류 응답을 받습니다. 위 서비스 조회 API는 읽기 전용입니다. 문서·관계 저장은 별도의 [문서 등록 API](docs/08_DOCUMENT_INGESTION.md#7-개발자를-위한-api와-처리-경계)를 사용하며 임의 Cypher 실행 기능은 없습니다. 개발 서버 종료는 해당 터미널에서 `Ctrl+C`를 누릅니다.

## 8. 테스트와 종료·재시작

코드의 자동 테스트는 다음 명령으로 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py test
```

기본 실행은 DB 연결을 대체한 단위 테스트를 수행하고 실제 DB 통합 테스트는 건너뜁니다. DB까지 포함한 수동 확인은 `check_neo4j` → `seed_graph` → `graph_query`를 순서대로 실행하고, Browser에서 11개 노드와 12개 관계를 확인합니다.

제공된 **별도의 실습 DB**에서 통합 테스트도 실행하려면 다음을 사용합니다. 이 테스트는 `.env`로 지정한 실제 Neo4j DB에 예제 데이터를 두 번 적재합니다. Django가 자동 생성하는 테스트 DB로 분리되지 않으므로 업무 DB를 연결한 상태에서는 실행하지 마세요.

```powershell
$env:NEO4J_INTEGRATION = "1"
.\.venv\Scripts\python.exe manage.py test
Remove-Item Env:\NEO4J_INTEGRATION
```

통합 테스트는 중복 적재, 서비스 목록, 문서 본문을 포함한 문맥 조회, 영향 후보, 없는 서비스의 오류 응답을 확인합니다. 이 작업 환경의 실제 검증 범위는 [검증 기록](docs/VALIDATION.md)을 참고하세요.

오늘 실습을 끝낼 때는 다음 명령으로 DB 컨테이너를 내립니다.

```powershell
docker compose down
```

데이터는 Docker의 이름 있는 볼륨에 보관되어 다시 시작해도 유지됩니다.

```powershell
docker compose up -d
.\.venv\Scripts\python.exe manage.py check_neo4j
```

`docker compose down -v`의 `-v`는 **DB 데이터 볼륨까지 삭제**합니다. 일반 종료에는 붙이지 마세요.

## 다음에 코드를 바꾸려면

주요 파일의 역할은 다음과 같습니다.

| 파일 | 역할 |
| --- | --- |
| [compose.yaml](compose.yaml) | Neo4j와 선택 기능인 Ollama의 이미지, 포트, 데이터 볼륨, 상태 확인 |
| [config/settings.py](config/settings.py) | `.env`에서 Django·Neo4j·LLM 설정 읽기 |
| [graphlab/db.py](graphlab/db.py) | 드라이버 연결과 세션·오류 처리 |
| [graphlab/seed.py](graphlab/seed.py) | 예제 검증, 문서 본문 읽기, 제약 조건과 그래프 적재 |
| [graphlab/repository.py](graphlab/repository.py) | 재사용하는 Cypher 조회 함수 |
| [graphlab/views.py](graphlab/views.py) | 조회 결과를 HTTP JSON으로 반환 |
| [graphlab/graphrag.py](graphlab/graphrag.py) | 질문의 서비스 식별, 그래프 근거·문서·실행 Cypher 수집 |
| [graphlab/llm.py](graphlab/llm.py) | 사내 LiteLLM 또는 로컬 Ollama에 근거를 전달해 답변 요청 |
| [graphlab/rag_views.py](graphlab/rag_views.py) | GraphRAG 페이지·상태·근거 조회·답변 생성 API |
| [graphlab/ingestion.py](graphlab/ingestion.py) | 문서 관계 추출·검증, 미리보기 서명, Neo4j 저장 |
| [graphlab/document_management.py](graphlab/document_management.py) | 문서 목록·상세, 버전 확인, 관계 교체·철회와 삭제 |
| [graphlab/ingestion_views.py](graphlab/ingestion_views.py) | 문서 등록·관리 페이지와 조회·추출·저장·수정·삭제 API |
| [graphlab/templates/graphlab/graphrag.html](graphlab/templates/graphlab/graphrag.html) | GraphRAG 화면의 HTML 구조 |
| [graphlab/static/graphlab](graphlab/static/graphlab) | 그래프·Cypher·출처 표시를 위한 CSS와 JavaScript |
| [graphlab/management/commands](graphlab/management/commands) | Django 관리 명령 제공 |
| [tests](tests) | 단위 테스트와 선택 실행하는 실제 DB 테스트 |

1. `data/sample_graph.json`에서 가상의 서비스·팀·문서를 살펴봅니다.
2. `queries`에서 조회가 어떤 관계 방향을 따라가는지 확인합니다.
3. Python 코드에서 Neo4j 드라이버 호출과 Cypher를 찾아, 명령/API가 같은 조회 함수를 사용하는 흐름을 읽습니다.
4. 작은 새 서비스 하나와 관계 하나를 추가하고 다시 적재해 봅니다. 이미 사용한 고유 ID는 다른 대상에 재사용하지 않습니다.

향후 회사 프로젝트에 연결할 때는 기존 LiteLLM 연결 설정을 사용하고, 업무 데이터의 문서 수집·권한 필터링·출처 추적·문서 보존 및 승인 정책을 먼저 설계하세요. 이후 필요에 따라 임베딩 검색을 추가할 수 있습니다. 현재의 로컬 개발 서버를 그대로 공용 서비스로 배포하는 단계는 이 실습 범위에 포함하지 않습니다.
