"""JSON/JSONB parameter helpers for Postgres repositories."""

from __future__ import annotations

import json
from typing import Any


def jsonb_param(value: Any) -> str:
    """Return a JSON string that SQL can cast with ::jsonb."""
    return json.dumps(value if value is not None else {}, ensure_ascii=False)
