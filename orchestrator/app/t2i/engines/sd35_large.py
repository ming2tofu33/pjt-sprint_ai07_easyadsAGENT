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

        # free+balanced 공존 모드: 렌더 후 파이프라인 해제 → 다음 job의 Gemma가 GPU에 들어갈 자리 확보.
        if _env_truthy("EASYADS_SD35_RELEASE_AFTER_RENDER"):
            del result, pipe
            _release_pipeline()

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
                # gpu_type은 pricing.GPU_PRICES 조회 키(EVAL_GPU_PRICES_JSON={"L4":x}). 미설정이면 gpu_unpriced.
                "gpu_seconds": round(perf_counter() - started, 3),
                "gpu_type": _gpu_type(),
                **request.metadata,
            },
        )


def _env_truthy(name: str) -> bool:
    import os

    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _evict_local_llm() -> None:
    """free+balanced 공존: SD3.5 로드 전에 호스트 Ollama의 로컬 LLM(Gemma)을 VRAM에서 내린다.
    23GB L4에서 SD3.5(~22GB)와 로컬 LLM(q8 ~11GB)은 공존 불가 → 렌더 직전 축출. best-effort.
    EASYADS_LOCAL_LLM_BASE_URL 미설정(서빙/비-로컬)이면 no-op. fix.md #19/#20."""
    base = os.getenv("EASYADS_LOCAL_LLM_BASE_URL", "").strip()
    model = os.getenv("EASYADS_LOCAL_LLM_MODEL", "").strip()
    if not base or not model:
        return
    try:
        import json as _json
        import urllib.request as _u

        host = base.rstrip("/")
        if host.endswith("/v1"):
            host = host[:-3]
        # Ollama 네이티브 unload: keep_alive=0(+빈 prompt)이면 모델을 VRAM에서 내림.
        req = _u.Request(
            host + "/api/generate",
            data=_json.dumps({"model": model, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"},
        )
        _u.urlopen(req, timeout=30).read()
    except Exception:
        pass


def _release_pipeline() -> None:
    """렌더 후 SD3.5 파이프라인을 VRAM에서 해제(다음 job의 로컬 Gemma가 GPU에 들어갈 자리 확보).
    EASYADS_SD35_RELEASE_AFTER_RENDER=1일 때만(=free+balanced 공존 모드). premium+balanced는 캐시 유지(속도)."""
    global _PIPELINE
    _PIPELINE = None
    try:
        import gc

        import torch  # type: ignore

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _gpu_type() -> str | None:
    """GPU 모델명(가격 조회 키). EASYADS_SD35_GPU_TYPE 우선, 없으면 torch가 보고하는 디바이스명(예: 'NVIDIA L4')."""
    forced = os.getenv("EASYADS_SD35_GPU_TYPE", "").strip()
    if forced:
        return forced
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return None


def _load_pipeline(model_ref: str | None):
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    # 로드 직전 로컬 LLM(Gemma) 축출 → SD3.5가 GPU 전체를 쓸 수 있게(공존 OOM 방지).
    _evict_local_llm()

    try:
        import torch  # type: ignore
        from diffusers import StableDiffusion3Pipeline  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise T2IEngineUnavailableError("SD3.5 dependencies are unavailable.") from exc

    if not model_ref:
        raise T2IEngineUnavailableError("SD3.5 model reference is missing.")

    # RAM/VRAM 안전 로드. 박스: RAM ~15GB, VRAM ~22GB. 컴포넌트 fp16 실측:
    #   transformer 16G / CLIP-L 0.24G / CLIP-G 1.3G / T5-XXL 8.9G / VAE 0.16G.
    # 핵심 교훈(2026-06-07):
    #   * device_map="balanced"는 text_encoder_3=None(T5 드롭)을 무시하고 model_index 기준으로 T5(8.9G)까지
    #     GPU에 적재 → 17.7+8.9=26.6G 목표로 로드 중 ~21.78G에서 VRAM OOM. max_memory 캡도 무시됨.
    #   * 호스트 재부팅의 진범은 CPU RAM OOM(enable_model_cpu_offload / 풀 .to(cuda) 전 CPU 적재)이었다.
    #     VRAM OOM(torch.OutOfMemoryError)은 그냥 raise → 박스 안전. 따라서 CPU RAM만 안 건드리면 반복 시도 안전.
    # 채택 전략: device_map="balanced" 폐기. 16G transformer만 per-component device_map으로 GPU 직행 스트리밍
    #   (CPU 미경유) → 그 다음 소형 encoder/VAE(~1.7G)는 일반 로드(CPU 일시 1.7G<15G 안전) 후 .to("cuda").
    #   T5는 device_map이 없으니 text_encoder_3=None이 정상 적용돼 진짜로 빠진다 → GPU 총 ~17.7G.
    #   enable_model_cpu_offload는 절대 금지. T5도 쓰려면 EASYADS_SD35_USE_T5=1(VRAM 26G+ 필요, 이 박스 불가).
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

    drop_t5 = not _env_truthy("EASYADS_SD35_USE_T5")
    pipe_kwargs = dict(common)
    pipe_kwargs["low_cpu_mem_usage"] = True
    if drop_t5:
        pipe_kwargs["text_encoder_3"] = None
        pipe_kwargs["tokenizer_3"] = None

    if cuda and have_accelerate and drop_t5:  # pragma: no cover - heavy local opt-in only
        # 16G transformer를 per-component device_map={"":"cuda:0"}로 GPU에 직접 스트리밍(CPU RAM 미경유).
        from diffusers import SD3Transformer2DModel  # type: ignore

        transformer = SD3Transformer2DModel.from_pretrained(
            model_ref,
            subfolder="transformer",
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
            device_map={"": "cuda:0"},
            **({"token": token} if token else {}),
        )
        pipe_kwargs["transformer"] = transformer
        # 나머지 소형 컴포넌트만 from_pretrained(device_map 없음 → T5 드롭 정상 적용). CPU 일시 ~1.7G.
        _PIPELINE = StableDiffusion3Pipeline.from_pretrained(model_ref, **pipe_kwargs)
        # 전체 pipe.to("cuda")는 device_map된 transformer 때문에 막힘 → 소형 컴포넌트만 개별 이동.
        for _name in ("text_encoder", "text_encoder_2", "vae"):
            _comp = getattr(_PIPELINE, _name, None)
            if _comp is not None and hasattr(_comp, "to"):
                _comp.to("cuda")  # 각 ≤1.3G → 총 GPU ~17.7G(transformer는 이미 cuda)
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