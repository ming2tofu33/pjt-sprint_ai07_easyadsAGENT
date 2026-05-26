"""Dry-run candidate checks for EasyAds T2I engines."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.app.core.config import get_t2i_settings  # noqa: E402
from orchestrator.app.t2i.gpt_image2 import GPTImage2Engine  # noqa: E402
from orchestrator.app.t2i.prompts import resolve_negative_prompt  # noqa: E402
from orchestrator.app.t2i.schemas import T2IRequest  # noqa: E402


SMOKE_PROMPT = (
    "Korean BBQ restaurant campaign poster background, sizzling pork belly on a grill, "
    "warm amber lighting, professional commercial food photography, clean empty bottom area "
    "for text overlay, no text, no watermark"
)


DEFAULT_ENGINES = ["gpt_image_2", "sd35_large", "flux"]
VERSION_PACKAGES = ["diffusers", "transformers", "accelerate", "safetensors", "huggingface_hub", "sentencepiece", "protobuf", "openai"]


def run_candidate_check(
    engines: list[str] | None = None,
    include_api: bool = False,
    load_local: bool = False,
    generate_local: bool = False,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run cost-safe candidate checks and write JSON/Markdown reports."""
    settings = get_t2i_settings()
    selected = engines or DEFAULT_ENGINES
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_output_dir = Path(output_dir) if output_dir else settings.output_dir / "candidate_check" / timestamp
    if not image_output_dir.is_absolute():
        image_output_dir = PROJECT_ROOT / image_output_dir
    log_dir = PROJECT_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    image_output_dir.mkdir(parents=True, exist_ok=True)

    environment = inspect_environment()
    results: list[dict[str, Any]] = []
    for engine in selected:
        if engine == "gpt_image_2":
            results.append(check_gpt_image_2(image_output_dir, include_api=include_api, environment=environment))
        elif engine == "sd35_large":
            results.append(check_sd35_large(load_local=load_local, generate_local=generate_local, output_dir=image_output_dir, environment=environment))
        elif engine == "flux":
            results.append(check_flux(load_local=load_local, generate_local=generate_local, output_dir=image_output_dir, environment=environment))
        else:
            results.append(_base_result(engine=engine, error="unknown engine", environment=environment))

    report = {
        "created_at": datetime.now().isoformat(),
        "include_api": include_api,
        "load_local": load_local,
        "generate_local": generate_local,
        "output_dir": str(image_output_dir),
        "environment": environment,
        "results": results,
    }
    json_path = log_dir / "t2i_candidate_check.json"
    md_path = log_dir / "t2i_candidate_check.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    report["json_report_path"] = str(json_path)
    report["markdown_report_path"] = str(md_path)
    return report


def check_gpt_image_2(output_dir: Path, include_api: bool = False, environment: dict[str, Any] | None = None) -> dict[str, Any]:
    """Check OpenAI image API readiness without calling it unless requested."""
    started = time.perf_counter()
    settings = get_t2i_settings()
    environment = environment or inspect_environment()
    result = _base_result(
        engine="gpt_image_2",
        model=settings.gpt_image_model,
        required_env="OPENAI_API_KEY",
        env_present=bool(settings.openai_api_key),
        package_available=environment["openai_sdk_available"],
        environment=environment,
        notes="Default check does not call the API. Use --include-api for one paid smoke generation.",
    )
    if not include_api:
        result.update({"can_generate": False, "latency_ms": _elapsed_ms(started)})
        return result

    negative_prompt = resolve_negative_prompt(None, {"business_type": "restaurant"})
    engine = GPTImage2Engine(allow_api_call=True)
    request = T2IRequest(
        prompt=SMOKE_PROMPT,
        negative_prompt=negative_prompt,
        width=1024,
        height=1024,
        num_images=1,
        quality="draft",
        output_dir=str(output_dir),
        metadata={"job_id": "gpt-image-2-smoke", "business_type": "restaurant", "test_type": "candidate_check"},
    )
    generation = engine.generate(request)
    result.update(
        {
            "can_generate": generation.error is None,
            "output_path": generation.image_paths[0] if generation.image_paths else None,
            "latency_ms": generation.latency_ms,
            "error": generation.error,
        }
    )
    return result


def check_sd35_large(
    load_local: bool = False,
    generate_local: bool = False,
    output_dir: Path | None = None,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check SD3.5 Large local readiness without downloading by default."""
    settings = get_t2i_settings()
    result = check_local_diffusion_candidate(
        engine="sd35_large",
        model_id=settings.sd35_model_id,
        pipeline_class="StableDiffusion3Pipeline",
        load_local=load_local,
        generate_local=generate_local,
        output_dir=output_dir,
        environment=environment,
    )
    result["notes"] = "Default check avoids from_pretrained. RTX 3090 local validation is preferred before GCP L4."
    return result


def check_flux(
    load_local: bool = False,
    generate_local: bool = False,
    output_dir: Path | None = None,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check FLUX local readiness without downloading by default."""
    settings = get_t2i_settings()
    result = check_local_diffusion_candidate(
        engine="flux",
        model_id=settings.flux_model_id,
        pipeline_class="FluxPipeline",
        load_local=load_local,
        generate_local=generate_local,
        output_dir=output_dir,
        environment=environment,
    )
    result["notes"] = "FLUX is heavy; keep lazy/on-demand loading and avoid resident startup loading."
    return result


def check_local_diffusion_candidate(
    engine: str,
    model_id: str,
    pipeline_class: str,
    load_local: bool,
    generate_local: bool,
    output_dir: Path | None,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    settings = get_t2i_settings()
    environment = environment or inspect_environment()
    diffusers_available = environment["diffusers_available"]
    can_import_pipeline = False
    import_error = None
    if diffusers_available:
        try:
            diffusers = __import__("diffusers", fromlist=[pipeline_class])
            getattr(diffusers, pipeline_class)
            can_import_pipeline = True
        except Exception as exc:
            import_error = str(exc)
    else:
        import_error = "diffusers package missing"

    result = _base_result(
        engine=engine,
        model=model_id,
        required_env="HF_TOKEN",
        env_present=bool(settings.hf_token),
        package_available=diffusers_available,
        can_import_pipeline=can_import_pipeline,
        error=import_error,
        environment=environment,
    )
    if generate_local and not load_local:
        result.update({"can_load_model": False, "can_generate": False, "error": "--generate-local requires --load-local"})
        return result
    if not load_local:
        result.update({"can_load_model": False, "can_generate": False, "latency_ms": _elapsed_ms(started)})
        return result

    try:  # pragma: no cover - optional heavy path
        import torch
        diffusers = __import__("diffusers", fromlist=[pipeline_class])
        pipe_cls = getattr(diffusers, pipeline_class)
        pipe = pipe_cls.from_pretrained(model_id, token=settings.hf_token or None, torch_dtype=torch.float16)
        result["can_load_model"] = True
        if generate_local:
            pipe = pipe.to("cuda" if torch.cuda.is_available() else "cpu")
            image = pipe(SMOKE_PROMPT, num_inference_steps=4).images[0]
            output_dir = output_dir or settings.output_dir / "candidate_check"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{engine}_0.png"
            image.save(output_path)
            result.update({"can_generate": True, "output_path": str(output_path)})
        else:
            result["can_generate"] = False
    except Exception as exc:  # pragma: no cover - optional heavy path
        result.update({"error": str(exc), "can_load_model": False, "can_generate": False})
    result["latency_ms"] = _elapsed_ms(started)
    return result


def inspect_environment() -> dict[str, Any]:
    settings = get_t2i_settings()
    torch_info = inspect_torch()
    versions = {f"{name}_version": _package_version(name) for name in VERSION_PACKAGES}
    return {
        "python_version": platform.python_version(),
        **versions,
        "torch_version": torch_info.get("torch_version"),
        "diffusers_available": _package_available("diffusers"),
        "transformers_available": _package_available("transformers"),
        "accelerate_available": _package_available("accelerate"),
        "hf_token_present": bool(settings.hf_token),
        "openai_sdk_available": _package_available("openai"),
        "cuda_available": torch_info["cuda_available"],
        "cuda_device_name": torch_info["cuda_device_name"],
        "cuda_memory_gb": torch_info["cuda_memory_gb"],
        "torch_available": torch_info["torch_available"],
    }


def inspect_torch() -> dict[str, Any]:
    info = {"torch_available": _package_available("torch"), "torch_version": _package_version("torch"), "cuda_available": False, "cuda_device_name": None, "cuda_memory_gb": None}
    if not info["torch_available"]:
        return info
    try:
        import torch

        info["torch_version"] = str(torch.__version__)
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            index = torch.cuda.current_device()
            info["cuda_device_name"] = torch.cuda.get_device_name(index)
            props = torch.cuda.get_device_properties(index)
            info["cuda_memory_gb"] = round(props.total_memory / (1024**3), 2)
    except Exception as exc:
        info["error"] = str(exc)
    return info


def render_markdown_report(report: dict[str, Any]) -> str:
    environment = report.get("environment", {})
    lines = [
        "# T2I Candidate Check",
        "",
        f"Created: {report['created_at']}",
        f"Output dir: `{report['output_dir']}`",
        "",
        "## Environment",
        f"- python_version: `{environment.get('python_version')}`",
        f"- torch_version: `{environment.get('torch_version')}`",
        f"- diffusers_version: `{environment.get('diffusers_version')}`",
        f"- transformers_version: `{environment.get('transformers_version')}`",
        f"- accelerate_version: `{environment.get('accelerate_version')}`",
        f"- cuda_available: `{environment.get('cuda_available')}`",
        f"- cuda_device_name: `{environment.get('cuda_device_name')}`",
        f"- cuda_memory_gb: `{environment.get('cuda_memory_gb')}`",
        f"- hf_token_present: `{environment.get('hf_token_present')}`",
        f"- openai_sdk_available: `{environment.get('openai_sdk_available')}`",
        "",
    ]
    for item in report["results"]:
        lines.extend(
            [
                f"## {item['engine']}",
                f"- model: `{item.get('model')}`",
                f"- required_env: `{item.get('required_env')}`",
                f"- env_present: `{item.get('env_present')}`",
                f"- package_available: `{item.get('package_available')}`",
                f"- torch_available: `{item.get('torch_available')}`",
                f"- torch_version: `{item.get('torch_version')}`",
                f"- cuda_available: `{item.get('cuda_available')}`",
                f"- cuda_device_name: `{item.get('cuda_device_name')}`",
                f"- cuda_memory_gb: `{item.get('cuda_memory_gb')}`",
                f"- can_import_pipeline: `{item.get('can_import_pipeline')}`",
                f"- can_load_model: `{item.get('can_load_model')}`",
                f"- can_generate: `{item.get('can_generate')}`",
                f"- output_path: `{item.get('output_path')}`",
                f"- error: `{item.get('error')}`",
                f"- notes: {item.get('notes')}",
                "",
            ]
        )
    return "\n".join(lines)


def _base_result(environment: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    environment = environment or {}
    result = {
        "engine": None,
        "model": None,
        "required_env": None,
        "env_present": False,
        "package_available": False,
        "python_version": environment.get("python_version"),
        "torch_available": environment.get("torch_available"),
        "torch_version": environment.get("torch_version"),
        "diffusers_version": environment.get("diffusers_version"),
        "transformers_version": environment.get("transformers_version"),
        "accelerate_version": environment.get("accelerate_version"),
        "cuda_available": environment.get("cuda_available"),
        "cuda_device_name": environment.get("cuda_device_name"),
        "cuda_memory_gb": environment.get("cuda_memory_gb"),
        "hf_token_present": environment.get("hf_token_present"),
        "openai_sdk_available": environment.get("openai_sdk_available"),
        "can_import_pipeline": None,
        "can_load_model": None,
        "can_generate": None,
        "output_path": None,
        "latency_ms": 0,
        "error": None,
        "notes": None,
    }
    result.update(kwargs)
    return result


def _package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check EasyAds T2I candidates without paid/heavy work by default.")
    parser.add_argument("--include-api", action="store_true", help="Allow one GPT-image-2 API smoke generation.")
    parser.add_argument("--load-local", action="store_true", help="Allow local model from_pretrained attempts.")
    parser.add_argument("--generate-local", action="store_true", help="Allow local image generation after loading.")
    parser.add_argument("--engines", nargs="+", default=DEFAULT_ENGINES, help="Subset of engines to check.")
    parser.add_argument("--output-dir", default=None, help="Image output directory for generated smoke images.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    report = run_candidate_check(
        engines=args.engines,
        include_api=args.include_api,
        load_local=args.load_local,
        generate_local=args.generate_local,
        output_dir=args.output_dir,
    )
    print(json.dumps({"json_report_path": report["json_report_path"], "markdown_report_path": report["markdown_report_path"]}, ensure_ascii=False))
