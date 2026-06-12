from pathlib import Path


def test_orchestrator_dockerfile_copies_bundled_fonts():
    dockerfile = Path("Dockerfile.orchestrator").read_text(encoding="utf-8")

    assert "COPY assets/fonts ./assets/fonts" in dockerfile
