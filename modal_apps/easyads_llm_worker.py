"""EasyAds Gemma LLM worker — OpenAI-compatible chat completions on Modal GPU.

Deploy:
    modal deploy modal_apps/easyads_llm_worker.py

Endpoint URL 확인:
    modal app list  (또는 Modal dashboard → Apps → easyads-llm → Deployments)

그 URL을 .env에 설정:
    EASYADS_LOCAL_LLM_BASE_URL=https://<org>--easyads-llm-gemmaserver-serve.modal.run
    EASYADS_LOCAL_LLM_MODEL=google/gemma-3-4b-it

사전 준비:
    modal secret create easyads-hf-token HF_TOKEN=<hf_token>   # Gemma gated model 접근
    modal volume create easyads-hf-cache                         # HF 모델 캐시 (T2I와 공유)
"""

from __future__ import annotations

import os
import time
import uuid

import modal
from pydantic import BaseModel

APP_NAME = "easyads-llm"
MODEL_ID = os.environ.get("EASYADS_MODAL_LLM_MODEL_ID", "google/gemma-3-4b-it")
GPU_TYPE = os.environ.get("EASYADS_MODAL_LLM_GPU", "L40S")
SCALEDOWN_WINDOW = int(os.environ.get("EASYADS_MODAL_LLM_SCALEDOWN_SECONDS", "300"))
TIMEOUT = int(os.environ.get("EASYADS_MODAL_LLM_TIMEOUT_SECONDS", "600"))
MAX_MODEL_LEN = int(os.environ.get("EASYADS_MODAL_LLM_MAX_MODEL_LEN", "8192"))
GPU_MEM_UTIL = float(os.environ.get("EASYADS_MODAL_LLM_GPU_MEMORY_UTIL", "0.85"))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = 512
    temperature: float | None = 0.7
    top_p: float | None = 0.95
    stream: bool | None = False


vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.0-devel-ubuntu22.04",
        add_python="3.12",
    )
    .pip_install(
        "vllm>=0.6.0,<1",
        "transformers>=4.46.0,<5",
        "huggingface_hub>=0.26.0,<1",
        "fastapi>=0.110.0,<1",
        "pydantic>=2.0,<3",
    )
)

hf_cache_volume = modal.Volume.from_name("easyads-hf-cache", create_if_missing=True)
hf_secret = modal.Secret.from_name("easyads-hf-token")

app = modal.App(APP_NAME)


@app.cls(
    gpu=GPU_TYPE,
    image=vllm_image,
    volumes={"/root/.cache/huggingface": hf_cache_volume},
    secrets=[hf_secret],
    timeout=TIMEOUT,
    scaledown_window=SCALEDOWN_WINDOW,
)
@modal.concurrent(max_inputs=32)
class GemmaServer:
    @modal.enter()
    def load_model(self) -> None:
        from transformers import AutoTokenizer
        from vllm import LLM

        self.llm = LLM(
            model=MODEL_ID,
            dtype="bfloat16",
            gpu_memory_utilization=GPU_MEM_UTIL,
            max_model_len=MAX_MODEL_LEN,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

    @modal.asgi_app()
    def serve(self):
        import asyncio

        import fastapi
        from fastapi.responses import JSONResponse

        web_app = fastapi.FastAPI(title="EasyAds Gemma LLM")

        @web_app.get("/health")
        async def health():
            return {"status": "ok", "model": MODEL_ID}

        @web_app.post("/v1/chat/completions")
        @web_app.post("/chat/completions")
        async def chat_completions(body: ChatRequest):
            from vllm import SamplingParams

            prompt: str = self.tokenizer.apply_chat_template(
                [{"role": m.role, "content": m.content} for m in body.messages],
                tokenize=False,
                add_generation_prompt=True,
            )
            params = SamplingParams(
                max_tokens=body.max_tokens or 512,
                temperature=body.temperature if body.temperature is not None else 0.7,
                top_p=body.top_p if body.top_p is not None else 0.95,
            )
            outputs = await asyncio.to_thread(self.llm.generate, prompt, params)
            text = outputs[0].outputs[0].text if outputs else ""
            prompt_tokens = len(outputs[0].prompt_token_ids) if outputs else 0
            completion_tokens = len(outputs[0].outputs[0].token_ids) if outputs else 0
            return JSONResponse({
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": MODEL_ID,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            })

        return web_app
