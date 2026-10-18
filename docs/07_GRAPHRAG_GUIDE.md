# GraphRAG 페이지 실행과 이해하기

이 페이지는 **현재 Neo4j의 서비스·팀·문서를 실제로 조회한 뒤, 그 근거로 LLM 답변을 만드는 실습 화면**입니다. 근거 검색만 먼저 실행할 수도 있습니다. Python 3.14와 Django는 기존 프로젝트 환경을 그대로 사용합니다.

새 문서는 [문서 등록 페이지](http://127.0.0.1:8000/documents/)에서 입력하고, LLM이 추출한 관계를 검토한 뒤 저장할 수 있습니다. 저장 결과는 다음 GraphRAG 조회에 반영됩니다. 단계별 실습은 [문서 등록과 관계 추출](08_DOCUMENT_INGESTION.md)을 참고하세요.

저장한 문서는 [문서 관리 페이지](http://127.0.0.1:8000/documents/manage/)에서 확인·수정·삭제합니다. 문서 개정과 삭제로 바뀐 원문·관계는 다음 검색에 반영되며, 다른 문서가 뒷받침하는 관계는 유지합니다. 구체적인 처리 규칙은 [문서 관리 가이드](09_DOCUMENT_MANAGEMENT.md)에 있습니다.

사내에는 이미 로컬 LLM과 LiteLLM이 있으므로 **사내 사용 시에는 기존 LiteLLM을 연결**하세요. 현재 PC에서 별도로 실습하려면 제공된 Ollama 설정을 사용합니다. 두 방법은 같은 그래프 조회 코드를 사용하고 답변을 생성하는 연결만 다릅니다.

## 1. 화면을 먼저 열기

프로젝트 최상위 폴더에서 실행합니다. 아직 초기 설치를 하지 않았다면 [README](../README.md)의 Python 가상환경, `.env`, Neo4j 설치·예제 적재 절차부터 진행하세요. 이미 있는 `.env`를 `.env.example`로 덮어쓰지 않습니다.

```powershell
docker compose up -d neo4j
.\.venv\Scripts\python.exe manage.py check_neo4j
.\.venv\Scripts\python.exe manage.py seed_graph
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

[http://127.0.0.1:8000/graphrag/](http://127.0.0.1:8000/graphrag/)를 엽니다. Django가 실행 중인 터미널은 열어 둡니다. HTML 파일을 더블클릭하는 방식이 아니라, Django를 거쳐 실행되는 페이지입니다. 화면의 JavaScript·스타일은 저장소에 포함되며 외부 CDN을 필요로 하지 않습니다.

LLM이 아직 준비되지 않아도 **근거만 조회**하는 동작은 사용할 수 있습니다. 이 동작은 실제 Neo4j에서 결과를 읽습니다. 검색 결과를 LLM이 생성한 답변처럼 표시하지 않습니다.

## 2. 사내에서는 기존 LiteLLM 연결하기

LiteLLM은 사내 모델에 접근하는 공통 API 입구입니다. 이 프로젝트가 모델 파일을 직접 읽거나 LiteLLM 서버를 새로 설치하지는 않습니다.

사내 운영 문서에서 다음 값을 확인하여 사내 PC의 `.env`에 입력합니다.

| 필요한 값 | 의미 |
| --- | --- |
| API 기본 주소 | 사내 LiteLLM의 OpenAI 호환 API 주소. 보통 `/v1`까지 포함 |
| 모델 별칭 | 호출자가 요청할 `model` 이름. LiteLLM 설정의 `model_name`에 해당 |
| 호출용 API 키 | 해당 서버가 인증을 요구할 경우 발급받은 앱용 키 |

아래 주소와 모델명은 **실제 접속 정보가 아닌 예시**입니다. 본인의 사내 값으로 바꿉니다.

```dotenv
LLM_PROVIDER=litellm
LITELLM_BASE_URL=http://your-internal-llm-host:4000/v1
LITELLM_MODEL=your-internal-model-alias
LITELLM_API_KEY=
LITELLM_TIMEOUT=120
LITELLM_MAX_TOKENS=700
```

`LITELLM_API_KEY`는 인증이 필요한 경우 사내에서 발급받은 호출용 키를 입력합니다. 서버가 인증을 사용하지 않을 때만 비워 둡니다. 관리자 마스터 키를 받을 필요는 없습니다. 실제 키는 `.env`나 사내 비밀 설정에만 보관하며 Git에 올리지 않습니다. 화면과 브라우저 JavaScript에는 키를 넣지 않습니다. [LiteLLM 모델 별칭 설명](https://docs.litellm.ai/docs/proxy/configs), [호출용 가상 키](https://docs.litellm.ai/docs/proxy/virtual_keys)

`LITELLM_TIMEOUT`은 초 단위 대기 제한이고 `LITELLM_MAX_TOKENS`는 답변의 최대 출력 토큰 수입니다. 모델 서버가 바쁘거나 긴 답변이 필요하면 사내 운영 기준에 맞춰 조정합니다.

설정을 저장한 뒤 Django 서버를 `Ctrl+C`로 종료하고 다시 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

페이지에서 상태를 다시 확인합니다. 이 연결은 기본 주소 뒤에 `/models`를 붙여 모델 목록을 확인하고, `/chat/completions`에 질문과 근거를 보냅니다. 예시 기본 주소라면 요청 경로는 `/v1/models`, `/v1/chat/completions`입니다. 기본 주소에 `/chat/completions`까지 적으면 중복 경로가 되므로 넣지 않습니다. 사내 게이트웨이가 경로를 별도로 매핑한다면 그 API 기본 주소를 사용합니다. [LiteLLM API 사용 안내](https://docs.litellm.ai/docs/proxy/quick_start)

일부 사내 설정은 모델 목록 조회를 제한하면서 답변 생성은 허용할 수 있습니다. 따라서 LLM 상태 확인이 실패해도 Neo4j가 연결되어 있으면 **답변 생성**을 시도할 수 있습니다. 상태 표시와 실제 생성 결과를 함께 확인하세요.

모델명에는 Hugging Face 원본 이름이나 `ollama/...`를 추측하여 넣지 않습니다. 사내 LiteLLM이 클라이언트에게 공개한 별칭을 사용합니다. LiteLLM 자체는 내부·외부 모델을 모두 연결할 수 있으므로, 내부 모델을 가리키는 별칭을 지정해야 사내 처리 경로가 유지됩니다.

## 3. 현재 PC에서는 무료 로컬 Ollama 실행하기

사내 LiteLLM을 사용할 때는 이 단계를 생략합니다. 로컬 모델의 선정 이유와 무료 API 비교는 [무료 LLM 조사](06_FREE_LLM_OPTIONS.md)를 참고하세요.

### 3-1. 선택한 LLM 설정 넣기

현재 `.env`에 다음 항목을 추가하거나 기존 값을 수정합니다.

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_TIMEOUT=240
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_PREDICT=700
```

| 설정 | 의미 |
| --- | --- |
| `OLLAMA_BASE_URL` | Django가 접근하는 Ollama 서버 주소. `/api`는 붙이지 않음 |
| `OLLAMA_MODEL` | 내려받은 정확한 모델 태그 |
| `OLLAMA_TIMEOUT` | 답변을 기다리는 시간 제한, 초 단위 |
| `OLLAMA_NUM_CTX` | 모델 요청의 문맥 토큰 수. 크게 잡으면 메모리 사용 증가 |
| `OLLAMA_NUM_PREDICT` | 한 번의 답변에서 생성할 최대 토큰 수 |

### 3-2. 실행 프로그램과 모델 내려받기

인터넷이 되는 현재 개발 PC에서 실행합니다.

```powershell
docker compose --profile llm pull ollama
docker compose --profile llm up -d
docker compose exec ollama ollama pull qwen3.5:4b
docker compose exec ollama ollama list
```

`--profile llm`은 선택 기능인 Ollama 컨테이너를 함께 시작합니다. 기본 Compose는 CPU 실행 경로를 제공하며, GPU 사용은 장비·드라이버·컨테이너 런타임 설정에 따라 달라집니다. 모델이 다운로드되어 `ollama list`에 표시되는지 확인합니다. 모델 파일은 Docker의 볼륨에 보관됩니다. [Ollama Docker 실행 안내](https://docs.ollama.com/docker)

다음 두 가지는 별도 자원입니다.

- **Ollama 이미지:** 모델을 실행하는 프로그램.
- **Qwen 모델 파일:** 답변 생성에 사용하는 가중치와 관련 데이터.

프로그램 이미지만 받아서는 모델이 준비되지 않습니다. 첫 다운로드는 수 GB이므로 시간이 걸릴 수 있습니다. 첫 답변은 모델을 메모리에 올리는 시간도 포함합니다.

### 3-3. 연결 확인

```powershell
Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 5
```

설정된 모델이 목록에 있으면 Django를 재시작하고 페이지에서 질문합니다. Django 서버와 Ollama는 별도 프로세스이므로 둘 다 실행 중이어야 합니다. Ollama API는 `/api/chat`으로 대화를 요청하고 완성된 답변을 반환받을 수 있습니다. [공식 Chat API](https://docs.ollama.com/api/chat)

이미 Windows용 Ollama를 사용하는 경우 Docker의 Ollama 컨테이너는 시작하지 않아도 됩니다. 설치된 Ollama에서 `ollama pull qwen3.5:4b`를 실행하고 같은 `OLLAMA_BASE_URL`로 연결합니다. 같은 PC에서 네이티브 Ollama와 컨테이너 Ollama가 동시에 11434 포트를 사용하면 충돌합니다.

모델을 가볍게 바꾸려면 다음처럼 내려받고 `.env`의 `OLLAMA_MODEL`을 같은 이름으로 변경한 뒤 Django를 재시작합니다.

```powershell
docker compose exec ollama ollama pull qwen3:1.7b
```

## 4. 첫 질문과 예상 근거

처음에는 서비스 선택에서 대상을 명확히 지정하고 조회 종류를 바꿔 보세요. 자동 선택은 질문의 서비스 이름·ID 등을 찾는 규칙을 사용합니다. 서비스가 여러 개 언급되거나 대상을 정할 수 없으면 직접 선택해야 합니다.

| 선택 서비스 | 조회 종류 | 질문 예시 | 확인할 근거 |
| --- | --- | --- | --- |
| 주문 서비스 | 문맥 조회 / `context` | 주문 서비스의 담당팀과 의존 서비스, 관련 운영 문서를 알려줘. | 주문 → 커머스팀, 인증 → 플랫폼팀, 결제 → 결제팀, 세 서비스의 운영 문서 |
| 인증 서비스 | 영향 분석 / `impact` | 인증 서비스에 장애가 나면 어떤 서비스가 영향을 받을 수 있어? | 인증에 의존하는 주문·결제·알림 서비스와 연결 경로 |
| 결제 서비스 | 문맥 조회 / `context` | 결제 오류가 나면 어떤 문서를 보고 어디에 연락해야 해? | 결제 담당팀과 결제·인증 운영 문서 |

먼저 근거를 조회하고 관계·문서를 확인한 다음 답변을 생성해 보세요. 모델을 바꾸어도 같은 그래프 조회 조건이라면 검색 근거는 동일해야 합니다. 자연어 답변의 표현은 달라질 수 있습니다.

`impact`는 의존 관계를 따라 찾은 **영향 후보**입니다. 실제 장애 전파가 발생했다고 판단한 결과가 아닙니다. 그래프가 오래되었거나 관계가 빠져 있으면 결과도 그 영향을 받습니다.

## 5. 질문이 답변이 되는 과정

```text
① 질문 + 대상 서비스 + 조회 종류
        ↓
② Django가 서비스와 조회 범위를 결정
        ↓
③ 미리 작성한 Cypher를 파라미터와 함께 Neo4j에 실행
        ↓
④ 서비스·팀·문서의 사실과 출처를 수집
        ↓
⑤ 선택한 LLM에 질문 + 검색 근거 전달
        ↓
⑥ 답변, 검색 그래프, 문서, 실제 실행한 Cypher를 함께 표시
```

각 구성요소의 역할은 다음과 같습니다.

| 구성요소 | 하는 일 |
| --- | --- |
| Neo4j | 저장된 서비스, 담당팀, 의존 관계, 문서 원문을 조회 |
| Cypher | 어떤 관계 방향과 홉 수를 따라 검색할지 표현 |
| Django | 입력 검증, 조회 실행, 근거 구성, LLM 요청, 결과 반환 |
| LLM | 전달받은 근거를 읽고 질문에 맞춰 자연어로 설명 |
| 브라우저 | 질문 입력, 결과·연결 그래프·출처·Cypher 표시 |

GraphRAG 질문 처리에서 **LLM은 임의 Cypher를 생성하거나 DB를 수정하지 않습니다.** 개발자가 작성한 읽기 쿼리에 서비스 ID를 파라미터로 전달합니다. 화면의 Cypher 기록에는 실제 실행한 쿼리와 파라미터, 조회 행이 표시됩니다. 별도의 문서 등록 기능은 LLM이 추출한 후보를 사용자가 검토한 후 서버가 검증하여 저장하며, 이 경우에도 LLM이 만든 Cypher를 실행하지 않습니다.

`context`는 대상 서비스와 직접 의존하는 서비스, 그 팀·문서를 조회합니다. `impact`는 대상에 의존하는 서비스를 역방향으로 최대 5홉 탐색하고, 대상 및 영향 후보의 팀·문서를 모읍니다. 화면의 전체 그래프와 질문에 사용한 검색 그래프의 범위가 다를 수 있습니다.

문서 조회 본문은 문서당 최대 6,000자이고, LLM에 넘기는 본문은 문서당 최대 4,000자·문서 본문 합계 최대 14,000자로 제한됩니다. 데이터가 커지면 문서 원문 전체를 항상 모델이 읽는 구조가 아니므로, 청크 분할과 질문별 문단 선별을 추가해야 합니다. 원본 문서도 함께 확인하세요.

그래프 사실은 `[G]`, 문서는 `[D1]` 같은 출처 번호로 표시합니다. 번호는 검색 결과와 답변을 연결하기 위한 표기이며, 번호가 붙었다는 사실만으로 답변 내용이 검증되지는 않습니다. 존재하지 않는 출처 번호를 생성한 경우 답변을 오류로 처리하고, 출처를 표시하지 않으면 경고를 표시합니다. 근거와 내용이 일치하는지는 직접 확인하세요.

## 6. 개발자가 사용할 HTTP API

| 메서드·경로 | 용도 |
| --- | --- |
| `GET /graphrag/` | GraphRAG HTML 페이지 |
| `GET /api/graph/` | 현재 실습 그래프의 노드와 관계 |
| `GET /api/graphrag/status/` | Neo4j·선택한 LLM 상태와 서비스 목록 |
| `POST /api/graphrag/retrieve/` | LLM 없이 그래프 근거 조회 |
| `POST /api/graphrag/ask/` | 근거 조회 후 선택한 LLM으로 답변 생성 |

POST 요청 본문 형식:

```json
{
  "question": "주문 서비스의 담당팀과 관련 운영 문서를 알려줘.",
  "service_id": "order-service",
  "intent": "context"
}
```

`service_id`를 빈 문자열로 보내면 질문에서 대상을 찾습니다. `intent`는 `auto`, `context`, `impact` 중 하나입니다. 자동 판별은 간단한 규칙이므로 복잡한 질문은 대상과 조회 종류를 명시하는 것이 좋습니다.

검색 응답에는 `service`, `intent`, `facts`, `sources`, `graph`, `trace`, `scope`, `retrieval_ms`가 포함됩니다. 문서 `sources`에는 표시용 번호와 원문 ID, 제목, 원본 경로, 본문, 연결 서비스가 담깁니다. 생성 응답은 여기에 `answer`, `model`, `generation_ms`, `usage`, `citations`를 추가합니다. 출처 표기 문제는 `citation_warning`으로 표시될 수 있습니다.

API에는 Django CSRF 보호가 적용됩니다. 브라우저 페이지는 필요한 토큰을 포함합니다. 외부 도구로 POST를 테스트할 때도 페이지에서 받은 CSRF 쿠키와 토큰을 함께 전달해야 합니다. 테스트를 위해 CSRF 보호를 꺼 둘 필요는 없습니다.

## 7. 사내망으로 옮길 때

### 기존 사내 LiteLLM을 사용할 경우

1. 저장소와 [기본 오프라인 실행 자원](03_OFFLINE_SETUP.md)을 준비합니다.
2. 사내 PC에서 Neo4j와 Python 환경을 설치하고 예제 데이터를 적재합니다.
3. 사내 `.env`의 `LLM_PROVIDER`를 `litellm`으로 설정하고 사내 접속 정보를 입력합니다.
4. Neo4j 연결 → 근거만 조회 → 모델 상태 → 실제 답변 순서로 확인합니다.

이 경로에서는 Qwen 모델이나 Ollama 이미지 반입이 필수 사항이 아닙니다. LiteLLM과 모델 서버는 회사의 기존 운영 체계를 사용합니다.

### 별도 Ollama도 반입하고 싶은 경우

실행 프로그램 이미지와 모델 볼륨은 따로 옮깁니다. 아래 예시는 **제공된 Docker Compose와 같은 Ollama 버전·플랫폼을 사용하는 새 실습 환경**으로 옮기는 절차입니다. 기존 모델 데이터를 사용하는 환경은 먼저 백업하고 별도 실습 볼륨에서 검증하세요.

외부 개발 PC에서 모델 다운로드가 끝난 뒤 실행합니다. `offline` 폴더는 Git에서 제외됩니다.

```powershell
New-Item -ItemType Directory -Force offline
docker image save --output offline/ollama-image.tar ollama/ollama:0.40.6
docker compose exec ollama ollama list
docker compose exec ollama tar -cf /tmp/ollama-models.tar -C /root/.ollama models
docker compose cp ollama:/tmp/ollama-models.tar offline/ollama-models.tar
Get-FileHash offline/ollama-image.tar -Algorithm SHA256
Get-FileHash offline/ollama-models.tar -Algorithm SHA256
```

이미지 태그는 `compose.yaml`과 같아야 합니다. 나중에 Compose의 버전을 변경하면 위 저장 명령의 태그도 함께 변경합니다.

두 tar 파일, 해시 기록, `compose.yaml`, 모델의 원본 LICENSE와 모델 이름·Ollama 버전을 승인된 반입 경로로 옮깁니다. 모델만 아카이브하므로 `.ollama`의 개인 키 파일은 포함하지 않습니다. 압축 파일을 만드는 동안 모델을 다운로드·삭제하지 않습니다. 모델 파일과 아카이브가 함께 존재하므로 디스크 여유 공간도 필요합니다.

사내 새 실습 PC에서는 먼저 해시를 비교하고 이미지와 모델을 복원합니다. Neo4j 이미지도 기존 오프라인 문서의 절차로 준비되어 있어야 합니다.

```powershell
Get-FileHash offline/ollama-image.tar -Algorithm SHA256
Get-FileHash offline/ollama-models.tar -Algorithm SHA256
docker image load --input offline/ollama-image.tar
docker compose --profile llm up -d --pull never
docker compose cp offline/ollama-models.tar ollama:/tmp/ollama-models.tar
docker compose exec ollama tar -xf /tmp/ollama-models.tar -C /root/.ollama
docker compose restart ollama
docker compose exec ollama ollama list
```

이제 인터넷 없이 `/api/tags`와 실제 답변 생성을 확인합니다. `docker save/load`는 이미지용이며 모델 볼륨을 자동으로 포함하지 않습니다. 위 모델 아카이브는 저장 디렉터리를 옮기는 이 프로젝트용 절차입니다. [Ollama 모델 저장 경로](https://docs.ollama.com/faq), [Docker 볼륨 백업 원리](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes), [이미지 저장](https://docs.docker.com/reference/cli/docker/image/save/), [이미지 불러오기](https://docs.docker.com/reference/cli/docker/image/load/)

## 8. 문제가 생기면

| 증상 | 확인할 내용 |
| --- | --- |
| 페이지가 열리지 않음 | Django가 실행 중인지, URL이 `/graphrag/`인지 확인 |
| Neo4j 연결 실패 | `check_neo4j`, Docker 상태, 기존 `.env` 비밀번호 확인 |
| 서비스 목록이 비어 있음 | `seed_graph`가 성공했는지 확인 |
| 서비스가 모호하다고 나옴 | 서비스 선택에서 기준 대상을 직접 선택 |
| 근거는 나오는데 답변 생성 실패 | 검색은 성공한 상태. 선택한 제공자의 서버·모델·권한을 확인 |
| LiteLLM 401/403 | 발급 키, 모델 접근 권한, 키의 만료 상태 확인 |
| LiteLLM 모델이 없다고 나옴 | API에서 공개한 별칭인지, 해당 키로 조회 가능한 모델인지 확인 |
| LiteLLM 주소 404 | 기본 주소에 `/v1`을 잘못 중복하거나 `/chat/completions`를 미리 붙이지 않았는지 확인 |
| Ollama 연결 실패 | Ollama 컨테이너/앱 실행 상태와 `OLLAMA_BASE_URL` 확인 |
| Ollama 모델 없음 | `ollama list`에 `.env`의 모델 태그가 정확히 있는지 확인 |
| 답변 시간 초과 | CPU 사용·가용 메모리·첫 모델 로딩 확인. 더 작은 모델이나 사내 서버로 비교 |
| 답변이 잘리거나 출처가 빠짐 | 생성 길이와 모델의 근거 준수 여부 확인. 원문 근거와 대조 |
| `.env` 수정이 적용되지 않음 | Django 재시작. PowerShell 환경변수가 같은 항목을 덮어쓰는지도 확인 |

생성 실패 시 자동으로 다른 외부 LLM에 전송하지 않습니다. 검색 성공 후 생성에 실패한 경우에는 오류와 함께 확보한 검색 근거를 유지하여 확인할 수 있습니다.

## 9. 현재 범위와 다음 확장

이것은 저장된 관계를 조회해 답변 근거를 만드는 **작은 그래프 기반 RAG**입니다. 벡터 검색이나 Microsoft GraphRAG의 전체 파이프라인을 구현한 프로젝트는 아닙니다.

현재 지원하는 범위는 서비스 선택, 고정된 관계 탐색, 문서 근거, LLM 답변, 실행한 Cypher 확인, 문서 등록·관계 추출·검토 후 저장, 등록 문서 목록·수정·삭제입니다. 문서 등록은 텍스트 입력과 UTF-8 `.txt`/`.md`를 지원합니다. PDF/DOCX 파싱, 임베딩·벡터 검색, 대화 이력 저장, 사용자 로그인·문서별 권한, 대규모 검색은 아직 없습니다. 현재 페이지와 API는 로컬 개발 실습용입니다.

실제 회사 데이터로 확장할 때는 먼저 서비스 ID와 문서 출처를 안정적으로 관리하고, 사용자에게 보여 줄 수 있는 문서 범위를 조회 단계에서 제한하세요. 그다음 문서를 청크로 나누고, 질문과 관련된 문단을 선별하는 검색을 추가하면 현재 구조를 단계적으로 확장할 수 있습니다.
