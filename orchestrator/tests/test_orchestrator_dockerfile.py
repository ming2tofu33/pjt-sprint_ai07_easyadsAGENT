from pathlib import Path


def test_orchestrator_dockerfile_copies_bundled_fonts():
    dockerfile = Path("Dockerfile.orchestrator").read_text(encoding="utf-8")

    assert "COPY assets/fonts ./assets/fonts" in dockerfile


def test_orchestrator_runtime_requirements_include_postgres_checkpointer():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "langgraph-checkpoint-postgres==" in requirements
    assert "psycopg-pool==" in requirements


def test_orchestrator_runtime_requirements_include_import_time_vision_dependencies():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "numpy==" in requirements
    assert "Pillow==" in requirements


def test_orchestrator_dockerfile_verifies_postgres_checkpointer_import():
    dockerfile = Path("Dockerfile.orchestrator").read_text(encoding="utf-8")

    assert "import langgraph.checkpoint.postgres" in dockerfile


def test_orchestrator_dockerfile_verifies_import_time_vision_dependencies():
    dockerfile = Path("Dockerfile.orchestrator").read_text(encoding="utf-8")

    assert "import numpy" in dockerfile
