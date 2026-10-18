# 문제 해결

먼저 프로젝트 최상위 폴더에서 명령을 실행하고 있는지 확인합니다. 이 폴더에는 `manage.py`, `compose.yaml`, `requirements.txt`가 있습니다. 아래 예시는 Windows PowerShell입니다.

## Python이 실행되지 않거나 버전이 다릅니다

```powershell
python --version
Get-Command python
```

Python 3.14 설치 경로가 선택되어야 합니다. Microsoft Store 안내가 열리거나 다른 버전이 나오면 설치 경로와 Windows의 앱 실행 별칭을 확인합니다. 필요하면 Python 3.14 실행 파일의 실제 경로로 가상환경을 만듭니다.

```powershell
& 'C:\YOUR_PYTHON314_PATH\python.exe' -m venv .venv
```

위 경로는 예시이므로 실제 설치 경로로 바꾸세요. 잘못된 Python으로 이미 만든 가상환경의 버전은 패키지 설치만으로 바뀌지 않습니다. 새 이름의 가상환경을 만들어 다시 설치하거나, 기존 가상환경을 교체할 때는 해당 폴더가 이 프로젝트의 `.venv`인지 먼저 확인합니다.

`py` 명령에 설치된 Python이 없다고 나와도, `python --version`이 3.14를 올바르게 표시하면 이 문서의 `python` 경로로 진행할 수 있습니다.

## PowerShell에서 Activate.ps1 실행이 차단됩니다

이 실습은 활성화가 필요 없습니다. 다음처럼 가상환경 Python을 직접 사용합니다.

```powershell
.\.venv\Scripts\python.exe manage.py check
```

이 실습을 위해 시스템 전체의 스크립트 실행 정책을 변경하지 않아도 됩니다.

## ModuleNotFoundError: django 또는 neo4j

다른 Python을 사용했거나 의존성을 설치하지 않은 경우가 많습니다.

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

내부망에서는 위 설치 명령 대신 [오프라인 설치 명령](03_OFFLINE_SETUP.md#6-내부망-pc에서-설치하기)을 사용합니다.

## docker 명령 또는 docker compose 명령을 찾지 못합니다

Docker 실행 환경과 Compose가 설치되어 있는지 확인하고 새 PowerShell 창을 엽니다. 이 프로젝트는 `docker compose` 형식의 Compose v2 명령을 사용합니다. 설치와 관련된 회사 정책이 있다면 승인된 배포판을 사용하세요.

`Cannot connect to the Docker daemon` 등 엔진 연결 오류는 Docker가 설치되어 있어도 **실행되지 않은 상태**에서 발생할 수 있습니다. Docker Desktop을 실행하고 Linux 컨테이너 엔진이 준비되었는지 확인합니다.

## 이미지 다운로드가 실패합니다

```powershell
docker compose pull
```

인터넷 연결, 사내 프록시·레지스트리 정책, Docker 로그를 확인합니다. 내부망에서는 `pull`을 실행하지 않고 준비 PC에서 저장한 이미지를 `docker load`한 뒤 `docker compose up -d --pull never`로 시작합니다. 정확한 이미지 태그가 `neo4j:2026.09.0`인지 확인하세요.

## 7474 또는 7687 포트가 이미 사용 중입니다

기존 Neo4j나 다른 Docker 컨테이너가 실행 중인지 먼저 확인합니다.

```powershell
docker ps
Get-NetTCPConnection -LocalPort 7474,7687 -ErrorAction SilentlyContinue
```

무관한 프로세스를 임의로 종료하지 마세요. 포트를 바꾸려면 `compose.yaml`의 **호스트 쪽 포트**, `.env`의 `NEO4J_URI`, Browser 접속 주소를 함께 맞춰야 합니다. 컨테이너 내부 Bolt 포트는 그대로 `7687`을 사용해도 됩니다.

예를 들어 호스트 Bolt 포트를 `17687`로 매핑했다면 Python의 URI는 `bolt://127.0.0.1:17687`이 됩니다. `127.0.0.1` 바인딩은 유지하세요.

## check_neo4j에서 연결 실패 또는 ServiceUnavailable

```powershell
docker compose ps
docker compose logs --tail 80 neo4j
```

다음 순서로 확인합니다.

1. 컨테이너가 실행 중인가?
2. Neo4j가 초기화를 마치고 연결을 받을 준비가 되었는가?
3. `.env`의 `NEO4J_URI`가 `bolt://127.0.0.1:7687`인가?
4. 호스트 포트를 바꿨다면 URI도 맞췄는가?
5. 새로 연 터미널에서도 같은 현상인가?

`http://localhost:7474`는 사람용 Browser 주소이고, Python의 DB 접속 주소가 아닙니다. Python 드라이버에는 Bolt URI를 사용합니다.

## 비밀번호를 바꿨는데 인증에 실패합니다

Docker의 `NEO4J_AUTH`는 **빈 DB를 처음 생성할 때** 초기 비밀번호를 설정합니다. 이미 데이터 볼륨이 존재하면 `.env`를 바꾸고 컨테이너를 다시 시작해도 DB에 저장된 기존 비밀번호는 그대로입니다. [Neo4j 초기 인증 설정](https://neo4j.com/docs/operations-manual/current/docker/introduction/#docker-auth)

기존 비밀번호를 알고 있다면 먼저 `.env`를 DB의 현재 비밀번호와 맞춰 접속을 확인합니다. 비밀번호 자체를 변경할 경우에는 기존 계정으로 인증한 뒤 Neo4j의 계정 관리 절차로 DB 비밀번호를 변경하고, `.env`도 함께 갱신합니다.

기존 비밀번호를 모른다면 임의로 데이터 볼륨을 삭제하지 말고, 사내 DB라면 관리자에게 복구를 요청하세요. 개인의 버려도 되는 실습 DB를 완전히 다시 만드는 경우에도 **데이터 볼륨 삭제는 저장된 그래프를 모두 없애는 작업**임을 먼저 확인해야 합니다. 일상적인 종료 명령은 `docker compose down`입니다.

`.env`를 고친 후에는 Django 개발 서버도 재시작하세요. 이전에 PowerShell에서 설정해 둔 환경변수가 있으면 `.env` 값보다 우선 적용될 수 있으므로 해당 설정도 확인합니다. 로그를 공유할 때는 비밀번호와 실제 내부 접속 정보를 제거하세요.

## Browser에는 연결되는데 예제 노드가 없습니다

로그인한 DB가 `neo4j`인지 확인하고 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe manage.py seed_graph
```

Browser에서 다음을 조회합니다.

```cypher
MATCH (n:Lab) RETURN count(n) AS total;
```

예제만 적재했다면 11개입니다. `Lab`과 `Service`의 대소문자를 확인하세요. Browser와 Python이 서로 다른 Neo4j 인스턴스에 접속한 것은 아닌지도 확인합니다.

## seed_graph를 다시 실행했는데 노드 개수가 줄지 않습니다

정상적인 동작일 수 있습니다. 이 명령은 샘플 ID로 노드를 합치거나 생성하고 속성을 갱신하며, 그래프 전체를 초기화하지 않습니다. 파일에서 항목을 삭제해도 기존 DB의 해당 노드가 자동 삭제되지는 않습니다. 담당팀이나 의존 관계를 바꿔 다시 적재해도 이전 관계는 남습니다. 이때 담당팀이 둘 이상 연결되면 조회 결과가 중복되거나 기대한 담당팀과 달라질 수 있습니다.

직접 추가한 데이터가 있다면 전체 개수는 README의 11개와 다를 수 있습니다. 실제 업무 데이터의 삭제·갱신 정책은 별도로 설계해야 합니다.

## Django API에 접속되지 않습니다

`runserver`를 실행한 PowerShell 창이 살아 있고, 다음 명령으로 서버가 실행 중인지 확인합니다.

```powershell
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

DB의 Browser 주소 `7474`와 Django API 주소 `8000`을 구분하세요. 이미 8000 포트가 사용 중이면 `127.0.0.1:8001` 등으로 실행하고 브라우저의 주소도 변경할 수 있습니다.

- `404`: 경로와 서비스 ID를 확인합니다. 예: `order-service`, `auth-service`.
- DB 조회 오류 응답: `check_neo4j`와 Neo4j 로그부터 확인합니다.
- `DisallowedHost`: 기본 실습 주소인 `127.0.0.1` 또는 `localhost`를 사용합니다. 외부 공개 목적으로 `ALLOWED_HOSTS`를 무작정 넓히지 않습니다.

## 테스트는 통과했는데 DB 조회가 실패합니다

기본 실행되는 자동 단위 테스트는 코드의 결과 처리·입력·오류 처리를 확인하며, 실제 Neo4j 서버의 설치와 실행을 대신하지 않습니다. 실제 DB 통합 테스트는 `NEO4J_INTEGRATION=1`일 때만 실행합니다. 우선 다음을 별도로 실행하세요.

```powershell
.\.venv\Scripts\python.exe manage.py check_neo4j
.\.venv\Scripts\python.exe manage.py seed_graph
.\.venv\Scripts\python.exe manage.py graph_query services
```

실제 실행 검증 여부는 [검증 기록](VALIDATION.md)에 구분해 기록합니다.
