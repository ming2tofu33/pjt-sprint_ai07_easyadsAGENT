"""SD3.5 로컬 엔진을 graph lane에 연결하는 어댑터.

마케팅 그래프의 T2I 라우터(`t2i/router.py`)는 `BaseT2IEngine` ABC를 `T2IRequest`/`T2IResult`로
다룬다. 실제로 동작하는 SD3.5 엔진은 *다른* lane(`t2i/engines/sd35_large.py::SD35LargeLocalEngine`)에
있고 `T2IGenerationInput`/`T2IGenerationOutput`을 쓴다. 이 어댑터가 둘을 이어줘 그래프(그리고 eval)가
실 SD3.5 이미지를 렌더할 수 있게 한다.

무거운 의존성(`diffusers`/`torch`)은 `generate()` 안에서 지연 import한다. 그래서 이 모듈을 import해도,
다른 엔진을 실행해도 절대 끌어오지 않는다. 라우터는 `EASYADS_ENABLE_SD35_LOCAL=true`일 때만 이
어댑터를 반환하고, 아니면 기존 `NotImplementedT2IEngine`을 유지한다 → 플래그 OFF면 서빙 동작 불변.
SD35_ROUTER_BRIDGE.md, fix.md #7/#13 참고.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from orchestrator.app.t2i.base import BaseT2IEngine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult

# SD3.5-large 로컬은 768²까지만 ~23GB VRAM에 맞는다. 1024²는 이 박스에서 GPU OOM.
SD35_MAX_SIDE = 768


class SD35LargeGraphEngine(BaseT2IEngine):
    name = "sd35_large"

    def load(self) -> None:
        return None

    def unload(self) -> None:
        return None

    def is_loaded(self) -> bool:
        try:
            from orchestrator.app.t2i.engines import sd35_large as _engine_mod

            return getattr(_engine_mod, "_PIPELINE", None) is not None
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        from orchestrator.app.t2i.settings import load_t2i_settings

        settings = load_t2i_settings()
        enabled = settings.enable_sd35_local
        return {
            "available": enabled,
            "loaded": self.is_loaded(),
            "model_id": settings.sd35_model_id,
            "reason": None if enabled else "EASYADS_ENABLE_SD35_LOCAL=false",
        }

    def generate(self, request: T2IRequest) -> T2IResult:
        started = perf_counter()
        # 지연 import: SD3.5가 아닌 모든 import 경로에서 diffusers/torch를 안 끌어오게.
        from orchestrator.app.t2i.engines.base import T2IGenerationInput
        from orchestrator.app.t2i.engines.sd35_large import SD35LargeLocalEngine
        from orchestrator.app.t2i.settings import T2IEngineUnavailableError

        meta = dict(request.metadata or {})
        job_id = meta.get("job_id") or uuid4().hex
        output_dir = request.output_dir or str(_default_output_dir(job_id))

        # 해상도 클램프: SD3.5-large 로컬은 768²까지만 ~23GB VRAM에 맞고 1024²는 GPU OOM.
        # 더 큰 ad-format 요청이 박스를 크래시 못 내게 클램프하고 원본 크기는 메타에 기록한다.
        # DECISION_2026-06-05_sd35_real_render.md 참고.
        req_w, req_h = int(request.width), int(request.height)
        width = min(req_w, SD35_MAX_SIDE)
        height = min(req_h, SD35_MAX_SIDE)
        if (width, height) != (req_w, req_h):
            meta = {**meta, "sd35_requested_size": [req_w, req_h], "sd35_clamped_size": [width, height]}

        gen_input = T2IGenerationInput(
            job_id=job_id,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt or None,
            width=width,
            height=height,
            num_images=request.num_images,
            output_dir=output_dir,
            metadata=meta,
        )

        try:
            output = SD35LargeLocalEngine().generate(gen_input)
        except T2IEngineUnavailableError as exc:
            # 비활성/deps 없음/GPU 없음 → graceful 처리(그래프로 raise 안 함)
            return T2IResult(
                engine="sd35_large",
                image_paths=[],
                latency_ms=_elapsed_ms(started),
                width=request.width,
                height=request.height,
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                metadata={"engine_available": False},
                error=f"sd35_unavailable:{exc}",
            )

        image_paths = list(output.image_paths or [])
        return T2IResult(
            engine="sd35_large",
            image_paths=image_paths,
            seed=request.seed,
            latency_ms=int(output.latency_ms) if output.latency_ms is not None else _elapsed_ms(started),
            width=width,
            height=height,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            metadata=dict(output.metadata or {}),  # gpu_seconds 전달 → eval gpu_exact 비용
            error=None if image_paths else "sd35_no_image",
        )


def _elapsed_ms(started: float) -> int:
    return max(0, int((perf_counter() - started) * 1000))


def _default_output_dir(job_id: str) -> Path:
    from orchestrator.app.core.config import get_t2i_settings

    return Path(get_t2i_settings().output_dir) / job_id
