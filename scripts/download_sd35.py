"""RAM 안전하게 SD3.5-large 가중치를 로컬 디스크로 받는다.

snapshot_download는 파일을 디스크로 스트리밍한다(모델 로드 없음). 그래서 호스트의 ~15GB RAM을
절대 넘지 않는다. T5-XXL(text_encoder_3/*)은 T5-drop 로드 경로에 맞춰 기본 스킵하며,
EASYADS_SD35_USE_T5=1이면 함께 받는다. 중단해도 재개 가능.
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

from huggingface_hub import snapshot_download  # noqa: E402

REPO = os.getenv("EASYADS_SD35_MODEL_ID", "stabilityai/stable-diffusion-3.5-large")
DEST = os.getenv("EASYADS_SD35_LOCAL_PATH", "/home/spai0722/models/sd35-large")
TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")

ignore = None
if os.getenv("EASYADS_SD35_USE_T5", "").strip().lower() not in {"1", "true", "yes", "on"}:
    ignore = ["text_encoder_3/*", "text_encoders/t5xxl*"]

path = snapshot_download(
    repo_id=REPO,
    local_dir=DEST,
    token=TOKEN,
    ignore_patterns=ignore,
    resume_download=True,
)
print("DOWNLOADED_TO", path)
