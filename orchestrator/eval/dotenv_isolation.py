"""Pytest 플러그인: 단위 테스트를 로컬 `.env` 파일로부터 격리한다.

`orchestrator/tests/conftest.py`가 아니라 `orchestrator/eval/`에 둔다. develop이 자기
test 파일을 추가할 때 `git pull` 충돌이 안 나게 하기 위함. Makefile `test` 타깃에서 전역
로드: `pytest -p orchestrator.eval.dotenv_isolation`.

필요한 이유: 테스트는 `.env.example` 기본값(LLM 비활성, provider `mock`)을 단언하는데,
`config._get_env`는 OS env -> `.env` -> `docs/api_key.env` -> default 순으로 읽고, 이 박스의
`.env`는 *실제* eval용으로 설정돼 있다(`LLM_ENABLE_API_CALL=true`, `LLM_DEFAULT_PROVIDER=openai` ...).
테스트의 `monkeypatch.delenv`는 OS-env 층만 지우므로 `.env` 파일값(그리고 docker-compose가 컨테이너
OS env에 주입한 사본)이 여전히 이긴다 -> eval 설정 컨테이너에서 disabled-경로 테스트가 실패한다.

이 플러그인의 autouse fixture는 (1) `.env`/`api_key.env` 파일 층을 무력화하고 (2) eval 활성화
변수를 OS env에서 지워, 테스트가 코드 기본값으로 떨어지게 한다. OS env와 테스트별
`monkeypatch.setenv`는 여전히 우선한다. `.env`는 절대 건드리지 않으며, 운영/eval 실행은 이 모듈을
로드하지 않는다. fix.md #15 참고.
"""

from __future__ import annotations

import pytest

from orchestrator.app.core import config

# 이 박스의 `.env`가 설정하고 docker-compose가 컨테이너 OS env에도 주입하는 eval 활성화 변수들
# (파일값만이 아니라 실제 os.environ 엔트리). .env.example 기본 베이스라인으로 리셋한다.
# 개별 테스트는 각자 monkeypatch로 덮어쓸 수 있다.
_EVAL_ENV_VARS = (
    "LLM_ENABLE_API_CALL",
    "EASYADS_ENABLE_LLM_CALLS",
    "LLM_DEFAULT_PROVIDER",
    "EASYADS_LLM_PROVIDER",
    "T2I_ALLOW_API_CALLS",
    "EASYADS_FREE_USE_LOCAL",
    "LLM_OPENAI_TEXT_MODEL_NANO",
    "LLM_OPENAI_TEXT_MODEL_MINI",
    "LLM_OPENAI_TEXT_MODEL_FULL",
    "LLM_OPENAI_VISION_MODEL",
)


@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1) config._get_env가 읽는 .env / api_key.env 파일 층을 무력화
    monkeypatch.setattr(config, "_load_dotenv", lambda *args, **kwargs: {})
    # 2) 같은 변수를 OS env에서도 제거(compose가 .env를 OS env에 주입하므로) → 코드 기본값
    #    (LLM 비활성, provider "mock")으로 떨어지게 함.
    for var in _EVAL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
