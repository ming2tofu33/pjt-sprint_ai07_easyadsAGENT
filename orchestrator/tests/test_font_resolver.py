from PIL import ImageFont

from orchestrator.app.rendering.font_resolver import load_font, resolve_font_path


def test_font_resolver_falls_back_without_crash(monkeypatch):
    monkeypatch.setenv("EASYADS_FONT_PATH", "missing/font.ttf")

    font = load_font(24)

    assert isinstance(font, (ImageFont.ImageFont, ImageFont.FreeTypeFont))


def test_resolve_font_path_accepts_missing_preferred():
    path = resolve_font_path("missing/font.ttf")

    assert path is None or isinstance(path, str)
