"""Prompt renderer graph node."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchestrator.app.llm.metadata_builders import build_prompt_renderer_metadata
from orchestrator.app.llm.prompt_renderer import render_prompt_for_engine, render_prompt_spec_for_engine
from orchestrator.app.schemas.llm_marketing import ImagePrompt

if TYPE_CHECKING:
    from orchestrator.app.graph.state import MarketingState


SUPPORTED_RENDER_ENGINES = {"mock", "sd35_large", "flux", "flux2_klein_4b", "gpt_image_1", "gpt_image_2"}


def _effective_render_engine(engine: str) -> str:
    """렌더에 실제로 쓰일 엔진을 결정한다.

    GPT-image API lane은 항상 활성. 로컬 엔진(sd35_large/flux)은 각자의 enable 플래그
    뒤에 게이트된다 — OFF면 "mock" → 기본 서빙 동작 불변이고 운영자가 opt-in할 때만 바뀐다.
    SD35_ROUTER_BRIDGE.md, fix.md #7 참고.
    """
    if engine in {"gpt_image_1", "gpt_image_2"}:
        return engine
    if engine in {"sd35_large", "flux", "flux2_klein_4b"}:
        from orchestrator.app.t2i.settings import is_flux2_klein_enabled, load_t2i_settings

        settings = load_t2i_settings()
        if engine == "sd35_large" and settings.enable_sd35_local:
            return "sd35_large"
        if engine == "flux" and settings.enable_flux_local:
            return "flux"
        if engine == "flux2_klein_4b" and is_flux2_klein_enabled(settings):
            return "flux2_klein_4b"
    return "mock"


def prompt_renderer_node(state: MarketingState) -> dict[str, Any]:
    ad_format_spec = state.get("ad_format_spec") or {}
    layout_spec = state.get("layout_spec") or {}
    image_prompt_spec = state.get("image_prompt_spec")
    engine = state.get("engine") if state.get("engine") in SUPPORTED_RENDER_ENGINES else "mock"
    effective_engine = _effective_render_engine(engine)
    metadata = build_prompt_renderer_metadata(state, requested_engine=engine, effective_engine=effective_engine)
    if image_prompt_spec:
        output = render_prompt_spec_for_engine(
            image_prompt_spec=image_prompt_spec,
            engine=effective_engine,
            render_profile=state.get("render_profile", "balanced"),
            metadata=metadata,
        )
    else:
        image_prompt = ImagePrompt(**(state.get("image_prompt") or {}))
        output = render_prompt_for_engine(
            image_prompt=image_prompt,
            engine=effective_engine,
            width=int(ad_format_spec.get("width") or 1024),
            height=int(ad_format_spec.get("height") or 1024),
            render_profile=state.get("render_profile", "balanced"),
            metadata=metadata,
        )
    return {
        "engine": effective_engine,
        "prompt_render_output": output.model_dump(),
        "status": "rendering_prompt",
    }
