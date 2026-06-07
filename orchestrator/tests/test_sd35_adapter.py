"""SD3.5 graph 어댑터 + 라우터 게이팅 (GPU/diffusers 불필요 — 엔진은 가짜로 대체)."""

from __future__ import annotations

import orchestrator.app.t2i.engines.sd35_large as sd35_engine_mod
import orchestrator.app.t2i.sd35_adapter as adapter_mod
from orchestrator.app.t2i.engines.base import T2IGenerationOutput
from orchestrator.app.t2i.router import NotImplementedT2IEngine, get_t2i_engine
from orchestrator.app.t2i.sd35_adapter import SD35LargeGraphEngine
from orchestrator.app.t2i.schemas import T2IRequest, T2IResult


def _req(**kw):
    base = dict(prompt="a cozy cafe poster background", width=1024, height=1024, num_images=1)
    base.update(kw)
    return T2IRequest(**base)


def test_adapter_maps_engine_output_to_t2i_result(monkeypatch, tmp_path):
    captured = {}

    def fake_generate(self, gen_input):
        captured["input"] = gen_input
        return T2IGenerationOutput(
            engine="sd35_large",
            image_paths=[str(tmp_path / "sd35_large_0.png")],
            latency_ms=1234,
            metadata={"model": "sd3.5", "gpu_seconds": 4.2},
        )

    monkeypatch.setattr(sd35_engine_mod.SD35LargeLocalEngine, "generate", fake_generate)

    out = SD35LargeGraphEngine().generate(_req(output_dir=str(tmp_path), seed=7, metadata={"job_id": "job_x"}))

    assert isinstance(out, T2IResult)
    assert out.engine == "sd35_large"
    assert out.image_paths == [str(tmp_path / "sd35_large_0.png")]
    assert out.latency_ms == 1234
    assert out.width == 768 and out.height == 768  # 1024에서 클램프(VRAM 맞춤)
    assert out.seed == 7
    assert out.error is None
    assert out.metadata.get("gpu_seconds") == 4.2  # eval 비용용으로 그대로 전달됨
    # request 필드가 엔진 입력 계약으로 변환됐는지
    assert captured["input"].job_id == "job_x"
    assert captured["input"].output_dir == str(tmp_path)


def test_adapter_degrades_gracefully_when_unavailable(monkeypatch):
    from orchestrator.app.t2i.settings import T2IEngineUnavailableError

    def boom(self, gen_input):
        raise T2IEngineUnavailableError("SD3.5 dependencies are unavailable.")

    monkeypatch.setattr(sd35_engine_mod.SD35LargeLocalEngine, "generate", boom)

    out = SD35LargeGraphEngine().generate(_req())

    assert isinstance(out, T2IResult)  # 그래프로 raise 안 함
    assert out.image_paths == []
    assert out.error and out.error.startswith("sd35_unavailable:")


def test_adapter_flags_missing_image(monkeypatch):
    def empty(self, gen_input):
        return T2IGenerationOutput(engine="sd35_large", image_paths=[], latency_ms=10, metadata={})

    monkeypatch.setattr(sd35_engine_mod.SD35LargeLocalEngine, "generate", empty)
    out = SD35LargeGraphEngine().generate(_req())
    assert out.error == "sd35_no_image"


def test_router_returns_notimplemented_when_disabled(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "false")
    engine = get_t2i_engine("sd35_large")
    assert isinstance(engine, NotImplementedT2IEngine)


def test_router_returns_adapter_when_enabled(monkeypatch):
    monkeypatch.setenv("EASYADS_ENABLE_SD35_LOCAL", "true")
    engine = get_t2i_engine("sd35_large")
    assert isinstance(engine, SD35LargeGraphEngine)
