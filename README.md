# pjt-sprint_ai07_easyadsAGENT

EasyAds / 개떡찰떡 프로젝트입니다.

현재 브랜치의 범위는 T2I-first MVP를 위한 공통 데이터 계약과 monorepo 기본 구조 정리입니다.

## 현재 구조

- `orchestrator/app/graph/state.py`: LangGraph 공유 상태 타입
- `orchestrator/app/schemas/marketing.py`: Validator, Options, Refactoring, T2I, Overlay, Validation 공통 Pydantic schema
- `orchestrator/tests/test_agent_schema_imports.py`: schema import 및 최소 인스턴스 테스트
- `docs/marketingstate-structure.md`: MarketingState/schema 설계 메모
- `docs/project_structure.txt`: 목표 monorepo 구조 원문
- `docs/secrets.md`: API key / token 관리 규칙

## Test

```bash
python -m pytest orchestrator/tests
```

## Development setup with uv

Use the Python version recommended in `.python-version`.

Recommended lockfile workflow:

```powershell
uv venv
uv sync --group dev
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

Compatibility requirements workflow:

```powershell
uv venv
uv pip sync requirements.txt requirements-dev.txt
uv run python scripts\check_uv_env.py
uv run python -m compileall orchestrator
uv run python -m pytest orchestrator\tests
```

Detailed setup is in `docs/uv-setup.md`.

GPU/local image generation workers for SD3.5 or FLUX should follow `docs/gpu-cu118-setup.md`. General backend, LangGraph, LLM, Vision, and mock T2I work does not require GPU requirements. The default `uv sync --group dev` path does not install torch or CUDA packages.

## Web UI

The Next.js frontend lives in `apps/web`.

```bash
cd apps/web
npm install
npm run dev
```

Open `http://127.0.0.1:3000/generate/chat` for the scenario C chat-start UI.

Validation commands:

```bash
cd apps/web
npm run lint
npm run test
npm run build
npm run e2e
```

## Secret Policy

`.env`, `*.env`, 모델 파일, 출력물, 캐시는 git에 올리지 않습니다. 실제 API key는 로컬 `.env` 또는 배포 환경변수로 관리합니다.
