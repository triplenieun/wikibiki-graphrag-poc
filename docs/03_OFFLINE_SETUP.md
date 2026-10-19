# Python 3.10.12와 사내 LiteLLM으로 내부망에서 실행하기

이 문서는 **사내 Python이 3.10.12이고, Docker 이미지를 인터넷에서 받을 수 없는 환경**을 기준으로 합니다. 인터넷이 가능한 **준비 PC**에서 Neo4j 이미지와 Python 패키지를 파일로 받아 반입하고, **사내 PC**에서 설치합니다. LLM은 기존 사내 LiteLLM을 호출하므로 Ollama 이미지나 LLM 모델 파일은 필요하지 않습니다.

Git clone에는 코드와 문서만 포함됩니다. `.env`, Python 패키지, Docker 이미지, DB 데이터는 포함되지 않습니다. 회사가 승인한 패키지 저장소·파일 반입 절차를 사용하세요.

## 1. 사내 PC에서 먼저 확인할 정보

| 항목 | 필요한 정보 |
| --- | --- |
| Python 실행 파일 | 실제로 Python 3.10.12를 실행하는 명령 또는 절대 경로 |
| Python을 실행할 OS·CPU | 예: Linux x86_64 또는 Windows AMD64 |
| Docker 실행 환경 | Docker Engine/Desktop과 Compose가 설치되어 있고 실행 가능한지 |
| Docker 이미지 플랫폼 | 아래 예시는 `linux/amd64`. ARM이면 대상 플랫폼에 맞춰 준비 |
| LiteLLM 연결 정보 | API 기본 주소, 호출 가능한 모델 별칭, 앱용 API 키 |
| Neo4j 사용 방식 | 아래는 새 로컬 실습 DB. 기존 사내 Neo4j를 쓰면 이미지 반입·Docker 단계 생략 |

Linux에서는 다음 명령을 실행합니다. `python3.10` 명령이 없다면 담당자가 알려 준 Python 실행 파일 경로로 바꿉니다.

```bash
python3.10 -c "import sys, platform; print(sys.version); print(sys.executable); print(platform.system(), platform.machine())"
docker version
docker compose version
docker info --format '{{.OSType}}/{{.Architecture}}'
```

Windows PowerShell에서는 다음과 같습니다. `python`이 다른 버전을 가리키면 사내 Python 3.10.12 실행 파일의 경로를 사용합니다.

```powershell
python -c "import sys, platform; print(sys.version); print(sys.executable); print(platform.system(), platform.machine())"
docker version
docker compose version
docker info --format '{{.OSType}}/{{.Architecture}}'
```

Python 출력이 **3.10.12**인지 확인하세요. 이 문서는 사내에 이미 설치된 런타임을 사용합니다. Python 3.10.12는 공식 Windows 설치 파일이 제공되지 않는 릴리스이므로, 별도의 Windows 설치 파일을 내려받는 절차를 가정하지 않습니다. [Python 3.10.12 공식 릴리스 안내](https://www.python.org/downloads/release/python-31012/)

Windows에서도 Neo4j는 **Linux 컨테이너**로 실행합니다. Docker Desktop/Engine과 필요한 WSL 2 등 실행 기반은 이미지 tar와 별개입니다. Docker 자체가 없다면 담당자에게 승인된 설치 파일과 OS 구성요소를 요청하세요. 이미지 파일만 반입해서는 Docker가 설치되지 않습니다.

기존 사내 Neo4j를 쓰면 URI·계정·DB 이름을 받아 아래 `.env`에 설정합니다. 예제 적재는 데이터를 쓰는 작업이므로 별도 실습 DB를 사용하세요.

## 2. 준비 PC: 사용할 소스 버전 받기

인터넷이 가능한 PC에서 실행합니다.

```bash
git clone https://github.com/triplenieun/wikibiki-graphrag-poc.git
cd wikibiki-graphrag-poc
git rev-parse HEAD
```

마지막 명령의 커밋 ID를 기록합니다. 코드, `requirements.txt`, `compose.yaml`, 반입 파일을 같은 버전 기준으로 준비해야 합니다. 이미 clone한 폴더라면 해당 폴더에서 준비해도 됩니다.

## 3. 준비 PC: Python 3.10.12용 패키지 받기

설치 파일인 **wheel**을 `offline/wheels`에 모읍니다. Python 3.14용 `.venv`를 사내로 복사하지 않습니다. 사내 PC에서 Python 3.10.12 가상환경을 새로 만듭니다.

준비 PC가 대상과 같은 OS·CPU이고 Python 3.10.12도 있다면 해당 Python으로 다운로드하는 방법이 우선입니다.

Linux:

```bash
mkdir -p offline/wheels
python3.10 -m pip download --only-binary=:all: --dest offline/wheels -r requirements.txt
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force offline\wheels
python -m pip download --only-binary=:all: --dest offline\wheels -r requirements.txt
```

준비 PC의 Python이 3.14처럼 다른 버전이라면 위 폴더를 만든 뒤 **대상을 명시해서 다운로드**합니다. 아래 두 가지 중 사내 Python 실행 환경에 맞는 명령 하나를 고릅니다. 준비 PC의 `python` 대신 `python3` 등 실제 명령을 사용해도 됩니다.

사내 대상이 **일반적인 glibc 기반 Linux x86_64**인 경우:

```bash
python -m pip download --only-binary=:all: --python-version 3.10.12 --implementation cp --abi cp310 --platform manylinux2014_x86_64 --dest offline/wheels -r requirements.txt
```

사내 대상이 **Windows x64**인 경우:

```powershell
python -m pip download --only-binary=:all: --python-version 3.10.12 --implementation cp --abi cp310 --platform win_amd64 --dest offline/wheels -r requirements.txt
```

`--only-binary=:all:`은 내부망에서 소스 빌드가 필요해지지 않도록 wheel만 받습니다. `--python-version 3.10.12`는 Python 버전 호환성을 확인하고, `--platform` 등은 대상 환경의 wheel을 선택합니다. Alpine Linux나 ARM CPU라면 위 Linux 명령을 그대로 쓰지 말고 대상에 맞는 환경에서 준비하세요. [pip 공식 다운로드 옵션](https://pip.pypa.io/en/stable/cli/pip_download/)

현재 `requirements.txt`에는 Python 3.10에서 필요한 `typing_extensions`도 명시되어 있습니다. 최신 파일을 사용하고, 해당 wheel을 누락하지 마세요. 다운로드 성공은 실제 사내 환경의 설치·실행 검증을 대신하지 않습니다. 같은 OS·Python 환경에서 준비하고 검증하는 방법이 우선입니다. 실패하면 버전 제한을 지우거나 `--ignore-requires-python`으로 우회하지 말고 대상 환경과 누락된 패키지를 확인합니다.

## 4. 준비 PC: Neo4j 이미지를 tar 파일로 저장하기

Docker가 실행 중이어야 합니다. 아래는 사내 Docker가 **Linux amd64(x86_64) 컨테이너**를 실행하는 경우입니다. 준비 PC가 Windows여도 Linux 컨테이너 모드에서 진행합니다.

```bash
docker pull --platform linux/amd64 neo4j:2026.09.0
docker image inspect neo4j:2026.09.0 --format '{{.Os}}/{{.Architecture}}'
docker save --output offline/neo4j-2026.09.0.tar neo4j:2026.09.0
```

이미지 정보가 `linux/amd64`인지 확인합니다. `docker save`는 이미지와 태그를 tar로 저장하며, 사내에서 `docker load`로 불러옵니다. 컨테이너의 DB 볼륨을 복사하는 작업이 아닙니다. **`docker export` 대신 `docker save`를 사용합니다.** [Docker save 공식 문서](https://docs.docker.com/reference/cli/docker/image/save/)

이 프로젝트의 `compose.yaml`이 참조하는 태그도 `neo4j:2026.09.0`이어야 합니다. 태그를 임의로 변경하거나 `latest`를 준비하지 마세요. 사내 LiteLLM을 사용하므로 Ollama 이미지와 모델은 받지 않습니다.

## 5. 반입 파일과 SHA-256 확인값 준비

반입할 파일은 다음과 같습니다.

- 같은 커밋의 프로젝트 소스와 문서 또는 Git bundle
- `offline/wheels` 아래 모든 `.whl` 파일
- `offline/neo4j-2026.09.0.tar`
- 위 파일의 SHA-256 목록과 기록한 Git 커밋 ID
- 실행 기반이 없는 경우: 회사에서 승인한 Docker 설치 파일과 필요한 OS 패키지
- 사용할 `.env`가 이미 있다면: 승인된 방법으로 별도 전달. 공개 저장소에 포함하지 않음

사내에서 GitHub나 사내 미러에 접속할 수 있으면 승인된 주소로 clone합니다. 접근할 수 없다면 준비 PC에서 **커밋된 소스**를 bundle로 만들 수 있습니다. 미커밋 수정은 bundle에 포함되지 않습니다.

```bash
git bundle create offline/wikibiki-graphrag.bundle --all
```

파일을 모두 준비한 후 프로젝트 루트에서 SHA-256 목록을 만듭니다. 기존 목록 자체는 계산에서 제외합니다.

Windows PowerShell:

```powershell
$offlineRoot = (Resolve-Path .\offline).Path
$checksums = @(Get-ChildItem -LiteralPath $offlineRoot -File -Recurse |
    Where-Object { $_.Name -ne 'SHA256SUMS' } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($offlineRoot.Length + 1).Replace('\', '/')
        $fileHash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$fileHash  $relativePath"
    })
[System.IO.File]::WriteAllText((Join-Path $offlineRoot 'SHA256SUMS'), ($checksums -join "`n") + "`n", [System.Text.Encoding]::ASCII)
```

Linux:

```bash
cd offline
find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
cd ..
```

`offline` 폴더 전체를 회사 절차에 따라 반입합니다. SHA-256 목록도 승인된 경로로 전달하고 사내 PC에서 비교합니다. 이 확인은 파일이 전달 중 바뀌었는지 판단하기 위한 것입니다.

## 6. 사내 PC: 코드와 반입 파일 배치·검증

GitHub 연결이 가능하면 2절과 같이 clone합니다. bundle을 반입했다면 다음 중 해당 OS의 명령을 사용합니다. 반입 경로는 실제 위치로 바꾸세요.

Linux:

```bash
git clone /APPROVED_TRANSFER/offline/wikibiki-graphrag.bundle wikibiki-graphrag-poc
cd wikibiki-graphrag-poc
```

Windows PowerShell:

```powershell
git clone C:\APPROVED_TRANSFER\offline\wikibiki-graphrag.bundle wikibiki-graphrag-poc
cd wikibiki-graphrag-poc
```

반입한 `offline` 폴더를 프로젝트 루트로 복사합니다. `manage.py`와 `offline`이 같은 폴더에 있어야 합니다. Git을 사용한 경우 `git rev-parse HEAD`로 준비 PC에서 기록한 커밋과 같은지도 확인합니다.

Linux에서 해시 검증:

```bash
cd offline
sha256sum --check SHA256SUMS
cd ..
```

Windows PowerShell에서 해시 검증:

```powershell
Get-Content .\offline\SHA256SUMS | ForEach-Object {
    $parts = $_ -split '  ', 2
    $filePath = Join-Path .\offline $parts[1]
    $actualHash = (Get-FileHash -LiteralPath $filePath -Algorithm SHA256).Hash
    if ($actualHash -ne $parts[0]) { throw "SHA-256 불일치: $($parts[1])" }
    Write-Output "OK: $($parts[1])"
}
```

파일 누락·불일치가 있으면 설치 전에 올바른 파일을 다시 반입합니다.

## 7. 사내 PC: Python 3.10.12 가상환경에 오프라인 설치

프로젝트 루트에서 실행합니다. 기존 Python 3.14 `.venv`는 재사용하지 말고 새로 clone한 폴더 등에서 시작하세요. 아래 명령은 Python 패키지 저장소에 접속하지 않습니다.

Linux:

```bash
python3.10 --version
python3.10 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links offline/wheels -r requirements.txt
.venv/bin/python -m pip check
```

Windows PowerShell:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links offline\wheels -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

`--version`이 3.10.12인지 확인한 다음 가상환경을 만드세요. `pip check`가 `No broken requirements found.`를 표시하면 설치된 의존성이 맞습니다. Linux에서 `venv`나 `ensurepip`가 없다는 오류가 나면 담당자에게 해당 Python 3.10용 가상환경 OS 패키지를 승인된 방식으로 설치해 달라고 요청합니다.

`No matching distribution found`는 wheel 누락이나 대상 Python·OS·CPU 불일치일 수 있습니다. 준비 PC에서 파일을 보충하세요. 이 프로젝트를 실행하기 위해 LiteLLM 서버나 LiteLLM Python 패키지를 새로 설치할 필요는 없습니다.

## 8. 사내 PC: `.env`를 사내 설정으로 수정

기존 `.env`를 복사했다면 해당 파일을 수정합니다. **기존 파일을 덮어쓰지 않도록** 파일이 없을 때만 예제에서 만듭니다.

Linux:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

Windows PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Linux에서는 사용하는 텍스트 편집기로 `.env`를 엽니다. 아래 `YOUR_...`는 실제 값으로 바꿉니다. 같은 항목이 있으면 중복 추가하지 말고 기존 줄을 수정하세요.

```dotenv
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=YOUR_NEO4J_PASSWORD
NEO4J_DATABASE=neo4j

DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_SECRET_KEY=YOUR_GENERATED_SECRET

LLM_PROVIDER=litellm
LITELLM_BASE_URL=http://YOUR_INTERNAL_LITELLM_HOST:4000/v1
LITELLM_MODEL=YOUR_DEPLOYED_MODEL_ALIAS
LITELLM_API_KEY=YOUR_APPLICATION_KEY
LITELLM_TIMEOUT=120
LITELLM_MAX_TOKENS=700
LLM_EXTRACTION_MAX_TOKENS=3000
```

- `LITELLM_BASE_URL`: 담당자가 준 API 기본 주소입니다. `/v1` 포함 여부를 확인하고 끝에 `/chat/completions`는 붙이지 않습니다.
- `LITELLM_MODEL`: 서버에 배포된 호출용 모델 별칭입니다. 모델 제품명으로 추측하지 않습니다.
- `LITELLM_API_KEY`: 해당 모델 권한이 있는 앱용 키입니다. 인증이 없는 사내 서버에서만 비워 둡니다.
- `LLM_PROVIDER=litellm`: 기본값 `ollama`에서 변경합니다. `OLLAMA_...` 항목은 남아 있어도 이 모드에서는 사용하지 않습니다.
- `NEO4J_PASSWORD`: 새 실습 DB의 비밀번호를 정합니다. 영문·숫자 16자 이상을 권합니다. 기존 DB는 발급받은 비밀번호를 사용합니다. `.env` 변경만으로 기존 DB 비밀번호가 바뀌지는 않습니다.
- `DJANGO_SECRET_KEY`: 기존 값이 있으면 유지합니다. 새 값은 아래 명령의 결과를 넣고 `.env`에만 보관합니다.

Linux:

```bash
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

기존 사내 Neo4j를 쓰면 연결 정보도 발급받은 값으로 바꾸고 다음 이미지 실행 단계를 건너뜁니다. `.env` 수정 후에는 Django를 재시작하세요. 같은 이름의 프로세스 환경변수가 이미 설정되어 있으면 그 값이 `.env`보다 우선합니다.

## 9. 사내 PC: 이미지 불러오고 Neo4j만 실행

프로젝트 루트에서 실행하며 Windows PowerShell과 Linux 모두 같은 명령을 사용합니다.

```bash
docker load --input offline/neo4j-2026.09.0.tar
docker image inspect neo4j:2026.09.0 --format '{{.Os}}/{{.Architecture}}'
docker compose up -d --pull never --wait --wait-timeout 240 neo4j
docker compose ps
```

`docker load`는 이미지와 태그를 복원합니다. `--pull never`는 외부 레지스트리에서 이미지를 받지 않도록 하고, 마지막 `neo4j`는 Neo4j 서비스만 실행하도록 지정합니다. 사내 LiteLLM 사용 시 `--profile llm`은 필요하지 않습니다. [Docker load 공식 문서](https://docs.docker.com/reference/cli/docker/image/load/), [Compose up 공식 문서](https://docs.docker.com/reference/cli/docker/compose/up/)

`neo4j`가 `healthy` 상태인지 확인합니다. 구형 Compose가 `--wait`를 지원하지 않으면 다음 명령으로 시작한 뒤 상태를 확인합니다.

```bash
docker compose up -d --pull never neo4j
docker compose ps
docker compose logs --tail 80 neo4j
```

이미지가 없다는 오류가 나면 `docker image ls neo4j`로 태그를 확인하세요. `docker load`가 성공했는지, 태그가 `compose.yaml`과 같은지 확인합니다. 문제 해결을 위해 `docker compose down -v`를 실행하지 마세요. `-v`는 DB 데이터가 들어 있는 볼륨도 삭제합니다.

## 10. 사내 PC: 연결 확인·예제 적재·웹 실행

한 줄씩 실행하고, 실패한 단계가 있으면 해결한 뒤 다음으로 진행합니다.

Linux:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py check_neo4j
.venv/bin/python manage.py seed_graph
.venv/bin/python manage.py graph_query context --service-id order-service
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check_neo4j
.\.venv\Scripts\python.exe manage.py seed_graph
.\.venv\Scripts\python.exe manage.py graph_query context --service-id order-service
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

`check`는 Django 설정을, `check_neo4j`는 DB 연결을 확인합니다. `seed_graph`는 예제 서비스·팀·문서와 관계를 넣고, `graph_query`는 주문 서비스의 연결 정보를 조회합니다. 이 프로젝트는 `manage.py migrate`가 필요하지 않습니다.

서버를 실행한 PC의 브라우저에서 다음 페이지를 엽니다.

| 페이지 | 주소 |
| --- | --- |
| GraphRAG 검색 | <http://127.0.0.1:8000/graphrag/> |
| 문서 등록·관계 추출 | <http://127.0.0.1:8000/documents/> |
| 문서 목록·수정·삭제 | <http://127.0.0.1:8000/documents/manage/> |

GraphRAG에서 주문 서비스를 선택하고 **근거만 조회**로 Neo4j 결과를 확인한 뒤 **답변 생성**으로 사내 LiteLLM 연결을 확인합니다. 문서 등록에서는 **관계 추출 → 미리보기 확인·수정 → 저장**을 확인합니다. 저장한 문서와 승인한 관계는 다음 GraphRAG 조회에 반영됩니다.

사내 LiteLLM이 `/models` 조회를 차단하면 상태 표시만 실패하고 실제 답변 생성은 성공할 수 있습니다. 인증 오류는 API 키와 모델 권한을, 경로 오류는 기본 주소와 `/v1` 포함 여부를 확인하세요. 자세한 설명은 [GraphRAG 가이드](07_GRAPHRAG_GUIDE.md)를 참고합니다.

이 절차는 실행 PC에서 접속하는 개인 실습용입니다. 원격 Linux 서버나 여러 사람이 접속하는 서비스로 배포하려면 접속 경로와 인증·문서 권한, 운영용 웹 서버 설정을 별도로 준비합니다.

## 11. 이후 업데이트할 때

코드·`requirements.txt`·Compose 이미지 태그를 같은 커밋 기준으로 전달합니다. 패키지가 바뀌면 Python 3.10.12 대상 wheel을 다시 준비하고, 이미지 태그가 바뀌면 새 tar를 반입합니다. `.env`는 사내 값을 유지합니다.

현재 구성은 사내 LiteLLM에 HTTP로 연결하며, 별도 임베딩 모델·APOC·Ollama 모델 다운로드가 필요하지 않습니다. `offline`, `.venv`, 실제 `.env`, DB 볼륨과 사내 원문은 GitHub에 올리지 않습니다.
