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

## Secret Policy

`.env`, `*.env`, 모델 파일, 출력물, 캐시는 git에 올리지 않습니다. 실제 API key는 로컬 `.env` 또는 배포 환경변수로 관리합니다.
