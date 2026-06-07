"""가드된 SD3.5 로컬 엔진 lane."""

from __future__ import annotations

import os
from pathlib import Path
from time import perf_counter

# CUDA 단편화를 줄여 768²의 ~22GB 피크가 23GB 카드에 맞게 한다. torch CUDA init 전에 설정해야 함
# (이 모듈은 첫 로드 직전에 지연 import됨). ※ 프로세스 env로 주는 게 더 확실(Makefile -e 참고).
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from orchestrator.app.t2i.engines.base import T2IGenerationInput, T2IGenerationOutput
from orchestrator.app.t2i.settings import (
    T2IEngineUnavailableError,
    get_hf_token,
    load_t2i_settings,
    require_t2i_enabled,
)

_PIPELINE = None


class SD35LargeLocalEngine:
    engine_name = "sd35_large"

    def generate(self, request: T2IGenerationInput) -> T2IGenerationOutput:
        started = perf_counter()
        settings = load_t2i_settings()
        require_t2i_enabled(self.engine_name, settings)

        model_ref = settings.sd35_local_path or settings.sd35_model_id
        pipe = _load_pipeline(model_ref)

        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = pipe(  # pragma: no cover - heavy local opt-in only
            prompt=request.prompt,
            negative_prompt=request.negative_prompt or "",
            width=request.width,
            height=request.height,
            num_images_per_prompt=min(request.num_images, settings.max_images_per_job),
            num_inference_steps=8,
            guidance_scale=4.0,
        )

        image_paths: list[str] = []
        for index, image in enumerate(getattr(result, "images", []) or []):
            path = output_dir / f"sd35_large_{index}.png"
            image.save(path)
            image_paths.append(path.as_posix())

        model_source = "local_path" if settings.sd35_local_path else "model_id"

        return T2IGenerationOutput(
            engine=self.engine_name,
            image_paths=image_paths,
            latency_ms=int((perf_counter() - started) * 1000),
            metadata={
                "model": settings.sd35_model_id if not settings.sd35_local_path else None,
                "model_source": model_source,
                "local_path_present": bool(settings.sd35_local_path),
                "hf_token_present": settings.hf_token_present,
                # eval 가격산정용 GPU-시간 단위(self_hosted -> gpu_exact). fix.md #13 참고.
                "gpu_seconds": round(perf_counter() - started, 3),
                **request.metadata,
            },
        )


def _env_truthy(name: str) -> bool:
    import os

    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _load_pipeline(model_ref: str | None):
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    try:
        import torch  # type: ignore
        from diffusers import StableDiffusion3Pipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise T2IEngineUnavailableError("SD3.5 dependencies are unavailable.") from exc

    if not model_ref:
        raise T2IEngineUnavailableError("SD3.5 model reference is missing.")

    # RAM/VRAM 안전 로드. 박스: RAM ~15GB, VRAM ~22GB. SD3.5 MMDiT transformer만 fp16 ~16GB.
    # 관측된 크래시 원인:
    #   * 파이프라인 전체를 CPU RAM에 적재 -> 호스트 OOM(재부팅 다수);
    #   * enable_model_cpu_offload는 GPU에 올린 16GB transformer를 다시 CPU RAM으로 끌어옴 -> 호스트 OOM.
    # 채택 전략(아래 코드): T5-XXL(~9.5GB)을 기본 드롭 + device_map="balanced"로 가중치를 GPU에 직행
    #   스트리밍(CPU에 16GB 적재 없음) + max_memory로 GPU 캡을 둬 활성화 여유 확보.
    #   enable_model_cpu_offload는 절대 쓰지 않음. T5도 쓰려면 EASYADS_SD35_USE_T5=1.
    common: dict[str, object] = {"torch_dtype": torch.float16}

    token = get_hf_token()
    if token:
        common["token"] = token

    cuda = torch.cuda.is_available()
    have_accelerate = False
    if cuda:  # pragma: no cover - heavy local opt-in only
        try:
            import accelerate  # type: ignore  # noqa: F401

            have_accelerate = True
        except Exception:
            have_accelerate = False

    pipe_kwargs = dict(common)
    if not _env_truthy("EASYADS_SD35_USE_T5"):
        pipe_kwargs["text_encoder_3"] = None
        pipe_kwargs["tokenizer_3"] = None

    if cuda and have_accelerate:  # pragma: no cover - heavy local opt-in only
        # device_map="balanced": accelerate가 로드 중 각 가중치를 최종 device로 바로 스트리밍 →
        # ~16GB transformer가 CPU RAM에 통째로 안 올라간다. 위에서 T5-XXL을 드롭했으므로 남은
        # ~18GB가 23GB GPU에 전부 들어가고 CPU엔 아무것도 안 남는다. enable_model_cpu_offload나
        # 별도 transformer 선로드는 일부러 안 함 — 그 조합이 16GB transformer를 CPU RAM으로 끌어와
        # 15GB 호스트를 OOM-kill 했음(워치독이 못 잡는 빠른 버스트). DECISION_2026-06-05_sd35_real_render.md 참고.
        pipe_kwargs["device_map"] = "balanced"
        pipe_kwargs["low_cpu_mem_usage"] = True
        # GPU 가중치 배치를 18GiB로 캡 → 768² 활성화용 ~5GB 여유(검증: 18GiB 캡이면 피크 ~22.6GB<23GB.
        # 없으면 balanced가 ~20.6GB로 과적재돼 로드 중 OOM). 넘치면 CPU로 흘려도 호스트 치명 아님.
        pipe_kwargs["max_memory"] = {0: "18GiB", "cpu": "12GiB"}
        _PIPELINE = StableDiffusion3Pipeline.from_pretrained(model_ref, **pipe_kwargs)
    else:
        _PIPELINE = StableDiffusion3Pipeline.from_pretrained(model_ref, **pipe_kwargs)
        if cuda:  # pragma: no cover
            _PIPELINE = _PIPELINE.to("cuda")

    # VAE 디코드 VRAM 스파이크를 줄여 768²가 23GB를 여유있게 통과하게.
    for _fn in ("enable_vae_tiling", "enable_vae_slicing"):  # pragma: no cover
        try:
            getattr(_PIPELINE, _fn)()
        except Exception:
            pass

    return _PIPELINE