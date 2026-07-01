"""Scan tracked files for forbidden runtime artifacts and literal credentials."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = ("data/uploads", "data/outputs", "playwright/.auth", "node_modules", ".next")
FORBIDDEN_NAMES = {".env", ".env.local", ".env.production"}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"(?i)(?:SUPABASE_SERVICE_ROLE_KEY|AWS_SECRET_ACCESS_KEY|R2_[A-Z_]*SECRET)"
        r"[ \t]*=[ \t]*[\"']?[A-Za-z0-9/+_-]{16,}"
    ),
)
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml", ".md", ".ini", ".txt"}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
    return [item for item in result.stdout.decode("utf-8").split("\0") if item]


def main() -> int:
    violations: list[str] = []
    for relative in tracked_files():
        normalized = PurePosixPath(relative).as_posix()
        if PurePosixPath(normalized).name in FORBIDDEN_NAMES or any(part in normalized for part in FORBIDDEN_PARTS):
            violations.append(f"forbidden tracked path: {normalized}")
            continue
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 1_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            violations.append(f"secret-like literal: {normalized}")
    if violations:
        raise SystemExit("security smoke failed:\n" + "\n".join(violations))
    print("security smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
