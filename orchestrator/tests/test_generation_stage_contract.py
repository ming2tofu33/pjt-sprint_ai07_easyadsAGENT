import json
from pathlib import Path
from typing import get_args

from orchestrator.app.api.schemas.generation_jobs import GenerationJobStatus
from orchestrator.app.generation_jobs.service import DEFAULT_STAGE_ORDER


def test_backend_progress_stages_are_listed_in_frontend_contract():
    contract_path = Path(__file__).resolve().parents[2] / "apps/web/types/contracts/generation-stages.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = set(contract["stages"])

    backend_known = {
        "queued",
        "modal_submitted",
        "modal_running",
        "t2i_running",
        "waiting_user_input",
        "completed",
        "failed",
        *DEFAULT_STAGE_ORDER,
    }

    assert backend_known <= expected


def test_terminal_generation_statuses_are_listed_in_backend_schema():
    backend_statuses = set(get_args(GenerationJobStatus))

    assert {"queued", "waiting_user_input", "completed", "failed"} <= backend_statuses
