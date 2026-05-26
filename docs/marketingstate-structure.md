# EasyAds / 개떡찰떡
## MarketingState 구조 초안 및 출력 JSON 스키마 확정 정리

## 1. 작업 개요

이번 작업은 실제 이미지 생성 모델을 연결하기 전, LangGraph 기반 마케팅 에이전트가 안정적으로 동작할 수 있도록 **공통 상태 구조와 노드별 출력 JSON 스키마를 먼저 확정한 작업**이다.

현재 작업 범위는 다음과 같다.

- `MarketingState` TypedDict 정의
- Validator / Options / Resume / Refactoring / T2I / Overlay / Validation 단계에서 사용할 Pydantic schema 정의
- API Key 및 Secret 관리 규칙 문서화
- schema import 및 최소 인스턴스 생성 테스트 추가
- 실제 LLM 호출, FastAPI endpoint, SD3.5 / FLUX / GPT-image-2 연결은 아직 구현하지 않음

이번 작업의 목적은 기능 구현이 아니라, **프론트엔드·백엔드·LangGraph·이미지 생성 엔진이 주고받을 데이터 계약을 먼저 고정하는 것**이다.

---

## 2. 추가된 핵심 파일

| 파일 | 역할 |
|---|---|
| `orchestrator/app/graph/state.py` | LangGraph 전체 노드가 공유하는 `MarketingState` 정의 |
| `orchestrator/app/schemas/marketing.py` | 각 노드와 API가 주고받을 Pydantic JSON schema 정의 |
| `orchestrator/tests/test_agent_schema_imports.py` | schema import 및 최소 생성 테스트 |
| `.env.example` | 팀 공유용 환경변수 예시 |
| `docs/secrets.md` | API Key / Secret 관리 규칙 |
| `.gitignore` | `.env`, 캐시, 출력물 등 git 제외 관리 |

---

## 3. MarketingState란 무엇인가?

`MarketingState`는 LangGraph의 `StateGraph` 안에서 각 노드가 공유하는 내부 상태 객체다.

즉, 사용자가 입력한 요청부터 시작해서, Validator 분석 결과, Options 질문, 사용자 선택값, Refactoring 결과, T2I 요청, 이미지 생성 결과, 텍스트 합성 설정, 최종 검증 결과까지 한 작업 흐름 전체를 담는 공용 상태 구조다.

쉽게 말하면 다음과 같다.

```text
MarketingState = LangGraph 전체 파이프라인이 들고 다니는 작업 상태 저장소