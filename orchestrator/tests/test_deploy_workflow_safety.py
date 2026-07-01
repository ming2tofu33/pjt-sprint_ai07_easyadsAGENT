from pathlib import Path

import yaml


WORKFLOW_PATH = Path(".github/workflows/deploy.yml")


def _load_workflow() -> dict:
    with WORKFLOW_PATH.open(encoding="utf-8") as file:
        return yaml.load(file, Loader=yaml.BaseLoader)


def _find_step(job: dict, *, uses: str | None = None, name: str | None = None) -> dict:
    for step in job["steps"]:
        if uses is not None and step.get("uses") == uses:
            return step
        if name is not None and step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step uses={uses!r} name={name!r}")


def test_deploy_workflow_runs_for_app_and_orchestrator_changes() -> None:
    workflow = _load_workflow()
    triggers = workflow["on"]

    for event_name in ("push", "pull_request"):
        paths = set(triggers[event_name]["paths"])
        assert "apps/**" in paths
        assert "orchestrator/**" in paths
        assert ".github/**" in paths


def test_pull_requests_never_push_docker_images_or_latest_tags() -> None:
    workflow = _load_workflow()
    build_job = workflow["jobs"]["build"]

    login_step = _find_step(build_job, uses="docker/login-action@v3")
    assert login_step["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"

    metadata_step = _find_step(build_job, uses="docker/metadata-action@v5")
    raw_latest_line = next(line for line in metadata_step["with"]["tags"].splitlines() if "value=latest" in line)
    assert "enable=${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}" in raw_latest_line

    build_step = _find_step(build_job, uses="docker/build-push-action@v6")
    assert build_step["with"]["push"] == "${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}"


def test_deploy_workflow_has_ci_quality_gates() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]

    assert "secret-scan" in jobs
    secret_scan_step = _find_step(jobs["secret-scan"], uses="gitleaks/gitleaks-action@v3")
    assert secret_scan_step["env"]["GITHUB_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"

    assert "web" in jobs
    web_steps = {step.get("name"): step for step in jobs["web"]["steps"]}
    assert "Run web tests" in web_steps
    assert "Run web type check" in web_steps
    assert "Run web lint" in web_steps
    assert web_steps["Run web type check"]["run"] == "npx tsc --noEmit"
    assert web_steps["Run web lint"]["run"] == "npm run lint"

    assert "bff" in jobs
    bff_steps = {step.get("name"): step for step in jobs["bff"]["steps"]}
    assert "Run BFF syntax check" in bff_steps
    assert "Run BFF tests" in bff_steps
