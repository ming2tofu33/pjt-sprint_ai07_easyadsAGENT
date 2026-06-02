"""DB file paths for the eval layer."""

from __future__ import annotations

import os

from orchestrator.app.core.config import _get_env

# RECORDS_DIR: /app/records in Docker (volume-mounted from /home/records).
# Override with RECORDS_DIR env var for local dev.
_RECORDS_DIR: str = os.environ.get("RECORDS_DIR", "/app/records")

OPS_DB_PATH: str = _get_env("EVAL_OPS_DB_PATH", os.path.join(_RECORDS_DIR, "easyads_ops.db"))
EVAL_DB_PATH: str = _get_env("EVAL_EVAL_DB_PATH", os.path.join(_RECORDS_DIR, "easyads_eval.db"))
