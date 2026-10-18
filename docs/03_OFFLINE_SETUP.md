# 내부망으로 옮겨 실행하기

Git clone은 **프로젝트 코드와 문서**를 가져옵니다. Python 설치 파일, Python 패키지, Docker 실행 환경, Neo4j 이미지는 별도로 준비해야 합니다. 이 문서는 인터넷이 가능한 준비 PC에서 필요한 자원을 모은 후 내부망 PC에서 실행하는 순서를 설명합니다.

회사에 승인된 Python 패키지 저장소나 컨테이너 레지스트리가 있다면 그 저장소를 사용하는 것이 우선입니다. 아래는 파일로 반입하는 경우의 예입니다. 실제 사내 데이터나 비밀번호는 이 공개용 예제 저장소에 넣지 않습니다.

## 1. 먼저 정할 항목

| 확인 항목 | 준비 기준 |
| --- | --- |
| 대상 OS와 CPU | 예: Windows x64. 준비 PC의 패키지 다운로드 환경도 일치시킵니다. |
| Python | 일반 Python 3.14 빌드와 동일한 아키텍처 |
| Docker 실행 환경 | 사내 승인 Docker Desktop/Engine 및 Compose, 필요한 OS 구성요소 |
| Neo4j 이미지 | `neo4j:2026.09.0`, 대상 Linux 컨테이너 아키텍처에 맞는 이미지 |
| Python 의존성 | 저장소의 `requirements.txt`에 고정된 전체 패키지 |
| 코드 버전 | Git 커밋 ID 또는 승인된 소스 압축본 |

Windows 호스트에서 Neo4j 이미지는 **Linux 컨테이너**로 실행합니다. Docker Desktop의 설치 파일과 Neo4j 이미지 tar는 서로 다른 파일입니다. WSL 2, 커널·배포판 등 회사 환경에 필요한 실행 기반도 미리 준비되어 있어야 합니다. 이미지 tar만으로 Docker 실행 환경이 설치되지는 않습니다.

회사에서 Docker를 사용할 수 없다면 기존 사내 Neo4j에 연결할 수 있습니다. 그 경우 URI·계정·DB 이름을 담당자에게 받아 `.env`에 설정하고 Compose 단계는 생략합니다. 이 실습의 적재는 쓰기 권한을 사용하므로 **별도의 실습 DB**를 사용해야 합니다. 직접 서버를 설치하는 경우의 Java·OS 호환성은 해당 Neo4j 버전의 [설치 요구사항](https://neo4j.com/docs/operations-manual/current/installation/requirements/)을 확인하세요.

## 2. 인터넷 가능한 준비 PC에서 패키지 받기

대상 PC와 **같은 OS·CPU·Python 3.14** 환경에서 진행합니다. Windows PowerShell 예시입니다. 프로젝트 루트에서 실행하세요.

```powershell
python --version
python -m venv .venv
New-Item -ItemType Directory -Force offline\wheels
.\.venv\Scripts\python.exe -m pip download --only-binary=:all: --dest .\offline\wheels -r requirements.txt
```

이미 실습용 `.venv`가 있다면 새로 만들 필요는 없습니다. 마지막 명령은 요구 패키지와 필요한 의존성의 설치 파일인 **wheel**을 받습니다. `--only-binary=:all:`은 반입 후 소스 빌드가 필요해지는 것을 피하기 위해 wheel만 허용합니다.

다운로드가 실패하면 해당 버전·OS·Python 조합에 맞는 wheel이 있는지 먼저 확인하세요. 임의로 버전 고정을 제거하거나, 인터넷이 없는 대상 PC에서 자동으로 빌드되기를 기대하지 않습니다. 대상 환경을 맞춘 준비 PC 또는 회사의 패키지 빌드 절차를 사용합니다.

패키지를 설치한 `.venv` 폴더를 다른 PC에 복사하는 방식은 사용하지 않습니다. 내부망 PC에서 가상환경을 새로 만들고 wheel로 설치합니다.

## 3. Neo4j 이미지를 파일로 저장하기

준비 PC의 Docker가 실행 중인 상태에서 진행합니다.

```powershell
docker pull neo4j:2026.09.0
docker image inspect neo4j:2026.09.0 --format '{{.Os}}/{{.Architecture}}'
docker save --output .\offline\neo4j-2026.09.0.tar neo4j:2026.09.0
```

대상이 일반적인 Windows x64의 Linux 컨테이너라면 `linux/amd64`인지 확인합니다. 준비 PC와 대상 PC의 아키텍처가 다르면 대상에 맞는 이미지 준비 절차가 필요합니다.

`docker save`는 실행 중 컨테이너의 사내 데이터를 복사하는 명령이 아니라 **이미지를 내보내는 명령**입니다. 이 프로젝트에서는 빈 Neo4j 이미지를 반입하고 내부망에서 예제 데이터를 적재합니다. [Neo4j 공식 오프라인 이미지 안내](https://neo4j.com/docs/operations-manual/current/docker/introduction/#docker-offline)

## 4. 반입할 파일 정리

다음을 회사 절차에 따라 반입합니다.

- 프로젝트 소스와 문서: `requirements.txt`, `compose.yaml`, `.env.example`, Python 코드, `data`, `queries`, `docs` 포함
- `offline/wheels`의 전체 wheel 파일
- `offline/neo4j-2026.09.0.tar`
- 대상 환경에 맞는 Python 3.14 설치 파일
- Docker와 필요한 OS 실행 기반 설치 파일: 아직 설치되지 않은 경우

`offline` 자원, `.venv`, 실제 `.env`, DB 볼륨, 사내 원문은 GitHub 코드 저장소에 올리지 않습니다. 대용량 이미지와 설치 파일은 회사가 승인한 별도 전달 경로를 사용합니다.

반입 검증용 SHA-256 목록을 생성할 수 있습니다.

```powershell
Get-ChildItem .\offline -File -Recurse | Get-FileHash -Algorithm SHA256 | Format-Table -AutoSize
```

준비 PC에서 생성한 목록을 별도로 보관하고 대상 PC에서 같은 파일의 해시를 비교합니다. 소스 버전도 함께 기록하세요.

```powershell
git rev-parse HEAD
```

위 Git 명령은 프로젝트가 Git 저장소이고 커밋이 존재할 때 사용합니다.

## 5. 코드 가져오는 방법 선택

### 사내에서 GitHub 또는 사내 미러에 접속할 수 있는 경우

회사에서 허용한 저장소 주소로 clone합니다.

```powershell
git clone https://YOUR_APPROVED_GIT_HOST/YOUR_GROUP/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

사내망에 GitHub 연결이 없다면 공개 GitHub 주소로 clone할 수 없습니다. 회사의 미러 저장소나 승인된 파일 반입 방법을 사용하세요.

### Git 이력을 파일로 옮기는 경우

준비 PC에서 **필요한 변경이 커밋된 Git 저장소**를 대상으로 bundle을 만들 수 있습니다. 미커밋 변경은 포함되지 않습니다.

```powershell
git bundle create .\offline\neo4j-lab.bundle --all
```

대상 PC에서 승인된 위치에 반입된 파일을 지정합니다.

```powershell
git clone C:\APPROVED_TRANSFER\neo4j-lab.bundle neo4j-lab
cd neo4j-lab
```

`C:\APPROVED_TRANSFER`는 실제 반입 경로로 바꿉니다. Git bundle과 별도로 wheel·이미지도 프로젝트의 `offline` 폴더에 복사합니다. Git 이력이 필요 없다면 소스 압축본을 반입해도 됩니다.

## 6. 내부망 PC에서 설치하기

Python 3.14와 Docker 실행 환경이 준비된 후, 프로젝트 루트에서 실행합니다. 여기서는 외부 패키지 저장소를 조회하지 않습니다.

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\offline\wheels -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
docker load --input .\offline\neo4j-2026.09.0.tar
docker image inspect neo4j:2026.09.0 --format '{{.Os}}/{{.Architecture}}'
```

`--no-index`는 PyPI 등 패키지 인덱스를 사용하지 않도록 하고, `--find-links`는 준비한 로컬 wheel 폴더를 지정합니다. 패키지 누락 오류가 나면 준비 PC에서 누락된 자원을 보충해야 합니다.

환경 파일을 최초 한 번 만들고 비밀번호를 직접 설정합니다.

```powershell
Copy-Item .env.example .env
notepad .env
```

외부에서 새 이미지를 받지 않도록 다음 명령으로 시작합니다.

```powershell
docker compose up -d --pull never
docker compose ps
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check_neo4j
.\.venv\Scripts\python.exe manage.py seed_graph
.\.venv\Scripts\python.exe manage.py graph_query context --service-id order-service
```

DB가 초기화 중이면 `check_neo4j`가 아직 실패할 수 있습니다. `docker compose logs --tail 80 neo4j`로 상태를 확인하고 연결 확인이 성공한 뒤 적재합니다. 이 프로젝트는 APOC, 별도 플러그인, 모델 다운로드를 요구하지 않습니다.

이후 [README의 Browser 조회와 API 실행](../README.md#6-neo4j-browser에서-그래프-보기)을 진행합니다.

## 7. 이후 업데이트할 때

코드·`requirements.txt`·Compose 이미지 버전을 **같은 소스 버전 기준**으로 전달합니다. Python 패키지가 바뀌면 해당 wheel도 새로 준비해야 하고, 이미지 태그가 바뀌면 새 이미지 tar가 필요합니다.

학습 코드를 기존 업무 프로젝트에 붙이기 전에 별도 환경에서 설치, 자동 테스트, DB 연결, 예제 조회를 확인하세요. 기존 Neo4j 데이터를 보유한 환경에서는 이미지 버전만 바꾸어 실행하지 말고 백업과 해당 버전의 업그레이드 절차를 먼저 확인합니다.

GraphRAG를 추가할 때는 사내 LLM 접속 방법 또는 모델 파일, 임베딩 모델, 문서 파서의 추가 의존성도 이 반입 목록에 포함해야 합니다. 현재 예제만 실행하는 데는 이러한 AI 자원이 필요하지 않습니다.
