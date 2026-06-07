"""DB file paths for the eval layer."""

from __future__ import annotations

import os

from orchestrator.app.core.config import _get_env

# RECORDS_DIR: /app/records in Docker (volume-mounted from /home/records).
# Override with RECORDS_DIR env var for local dev.
_RECORDS_DIR: str = os.environ.get("RECORDS_DIR", "/app/records")

OPS_DB_PATH: str = _get_env("EVAL_OPS_DB_PATH", os.path.join(_RECORDS_DIR, "easyads_ops.db"))
EVAL_DB_PATH: str = _get_env("EVAL_EVAL_DB_PATH", os.path.join(_RECORDS_DIR, "easyads_eval.db"))

# IMAGES_DIR: shared output for generated ad images so teammates can see them.
# The app hardcodes data/outputs/<job_id> (t2i_request_builder.py:83 — see fix.md),
# which is the local source tree, not the shared volume. Eval mirrors images here
# after each run. Default /app/records/images (= host /home/records/images).
IMAGES_DIR: str = _get_env("EVAL_IMAGE_DIR", os.path.join(_RECORDS_DIR, "images"))
