"""Qwen-VL：只从图片转写文字/代码，不解题。"""

from __future__ import annotations

import base64
import logging

from openai import APIConnectionError, APIStatusError, OpenAI

from backend.config import settings
from backend.errors import UpstreamServiceError

_logger = logging.getLogger(__name__)

_TRANSCRIBE_PROMPT = (
    "请只转写图中的文字、代码与公式，保持原有换行与顺序。"
    "不要解答问题，不要补充图中没有的内容，不要输出解释性前言。"
    "若几乎看不清文字，只输出空字符串。"
)


def extract_text_with_vision(
    image_bytes: bytes,
    *,
    mime_type: str = "image/png",
) -> str:
    """调用 Qwen-VL（OpenAI 兼容）转写图片文字。"""
    api_key = (settings.vision_api_key or "").strip()
    if not api_key:
        raise UpstreamServiceError("视觉模型未配置")
    if not image_bytes:
        raise ValueError("图片内容为空")

    media = (mime_type or "image/png").split(";")[0].strip().lower() or "image/png"
    if media == "image/jpg":
        media = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{media};base64,{b64}"

    client = OpenAI(
        base_url=settings.vision_base_url,
        api_key=api_key,
        timeout=settings.vision_timeout_seconds,
    )
    try:
        response = client.chat.completions.create(
            model=settings.vision_model,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": _TRANSCRIBE_PROMPT},
                    ],
                }
            ],
        )
    except (APIConnectionError, APIStatusError, TimeoutError) as exc:
        _logger.warning("vision extract failed: %s", exc)
        raise UpstreamServiceError("视觉模型调用失败") from exc
    except Exception as exc:
        _logger.warning("vision extract failed: %s", exc)
        raise UpstreamServiceError("视觉模型调用失败") from exc

    message = response.choices[0].message.content if response.choices else None
    return (message or "").strip()
