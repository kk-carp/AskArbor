"""图片识文：Qwen-VL 优先，PaddleOCR 兜底；成功后走既有问答。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from backend.errors import UpstreamServiceError
from backend.infra.ocr_engine import OcrEngineUnavailableError, extract_text_with_ocr
from backend.infra.vision_extract import extract_text_with_vision
from backend.schemas import OwnerInfo, SourceItem
from backend.services.qa_service import AskResult, answer_question

_logger = logging.getLogger("backend.audit")

ALLOWED_IMAGE_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/gif",
    }
)


class OcrFailedError(RuntimeError):
    """图片文字识别失败（工具失败，不是知识库未命中）。"""


@dataclass(frozen=True)
class OcrAskResult:
    answer: str
    hit: bool | None
    sources: list[SourceItem]
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    owner: OwnerInfo | None = None
    error_type: str | None = None
    extracted_text: str | None = None
    extract_method: str | None = None


def normalize_image_content_type(content_type: str | None, filename: str | None = None) -> str:
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw in ALLOWED_IMAGE_TYPES:
        return "image/jpeg" if raw == "image/jpg" else raw
    name = (filename or "").lower()
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image/jpeg"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".gif"):
        return "image/gif"
    raise ValueError("仅支持 PNG / JPEG / WEBP / GIF 图片")


def build_question_from_image(*, extracted_text: str, user_prompt: str | None) -> str:
    text = (extracted_text or "").strip()
    prompt = (user_prompt or "").strip()
    if prompt and text:
        return f"{prompt}\n\n【截图文字】\n{text}"
    if text:
        return text
    if prompt:
        return prompt
    raise OcrFailedError("未能从图片中识别出文字")


def extract_text_from_image(image_bytes: bytes, *, mime_type: str) -> tuple[str, str]:
    """返回 (text, method)；method 为 vision 或 ocr。"""
    vision_error: Exception | None = None
    try:
        text = extract_text_with_vision(image_bytes, mime_type=mime_type)
        if text:
            return text, "vision"
    except (UpstreamServiceError, ValueError) as exc:
        vision_error = exc
        _logger.info("ocr vision miss: %s", exc)

    try:
        text = extract_text_with_ocr(image_bytes)
        if text:
            return text, "ocr"
    except (OcrEngineUnavailableError, ValueError) as exc:
        _logger.info("ocr paddle miss: %s", exc)
        if vision_error is not None:
            raise OcrFailedError("图片识别失败") from exc
        raise OcrFailedError("图片识别失败") from exc

    raise OcrFailedError("未能从图片中识别出文字")


def ask_with_image(
    *,
    image_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    user_prompt: str | None,
    allowed_spaces: list[str],
    user_id: str,
    user_role: str,
    advisor_id: str | None,
    conversation_id: str | UUID | None,
) -> OcrAskResult:
    """全员可用：识图后按该用户 allowed_spaces 走既有问答。"""
    try:
        mime = normalize_image_content_type(content_type, filename)
        extracted, method = extract_text_from_image(image_bytes, mime_type=mime)
        question = build_question_from_image(extracted_text=extracted, user_prompt=user_prompt)
    except OcrFailedError as exc:
        _logger.info(
            "ask-ocr user_id=%s role=%s error=ocr_failed",
            user_id,
            user_role,
        )
        return OcrAskResult(
            answer="图片识别失败，请换更清晰的截图或改用文字提问。这不是知识库未命中。",
            hit=None,
            sources=[],
            conversation_id=None,
            ticket_id=None,
            owner=None,
            error_type="ocr_failed",
            extracted_text=None,
            extract_method=None,
        )
    except ValueError:
        raise

    result: AskResult = answer_question(
        allowed_spaces=allowed_spaces,
        question=question,
        user_id=user_id,
        user_role=user_role,
        advisor_id=advisor_id,
        conversation_id=conversation_id,
        screenshot_text=extracted,
    )
    _logger.info(
        "ask-ocr user_id=%s role=%s method=%s hit=%s",
        user_id,
        user_role,
        method,
        result.hit,
    )
    return OcrAskResult(
        answer=result.answer,
        hit=result.hit,
        sources=result.sources,
        conversation_id=result.conversation_id,
        ticket_id=result.ticket_id,
        owner=result.owner,
        error_type=result.error_type,
        extracted_text=extracted,
        extract_method=method,
    )
