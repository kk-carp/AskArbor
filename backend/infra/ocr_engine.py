"""PaddleOCR 兜底转写；未安装或未启用时不可用。"""

from __future__ import annotations

import logging
from typing import Any

from backend.config import settings

_logger = logging.getLogger(__name__)
_ocr_engine: Any | None = None
_ocr_load_attempted = False


class OcrEngineUnavailableError(RuntimeError):
    """本地 OCR 引擎不可用。"""


def _get_engine() -> Any:
    global _ocr_engine, _ocr_load_attempted
    if _ocr_engine is not None:
        return _ocr_engine
    if _ocr_load_attempted:
        raise OcrEngineUnavailableError("OCR 引擎不可用")
    _ocr_load_attempted = True
    if not settings.ocr_enabled:
        raise OcrEngineUnavailableError("OCR 引擎未启用")
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - 环境缺依赖
        _logger.warning("paddleocr import failed: %s", exc)
        raise OcrEngineUnavailableError("OCR 引擎未安装") from exc
    try:
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    except TypeError:
        # 新版本参数可能变化
        _ocr_engine = PaddleOCR(lang="ch")
    except Exception as exc:  # pragma: no cover
        _logger.warning("paddleocr init failed: %s", exc)
        raise OcrEngineUnavailableError("OCR 引擎初始化失败") from exc
    return _ocr_engine


def reset_ocr_engine_for_tests() -> None:
    global _ocr_engine, _ocr_load_attempted
    _ocr_engine = None
    _ocr_load_attempted = False


def extract_text_with_ocr(image_bytes: bytes) -> str:
    """用 PaddleOCR 转写；失败抛 OcrEngineUnavailableError。"""
    if not image_bytes:
        raise ValueError("图片内容为空")
    engine = _get_engine()
    try:
        result = engine.ocr(image_bytes, cls=True)
    except TypeError:
        result = engine.ocr(image_bytes)
    except Exception as exc:
        _logger.warning("paddleocr run failed: %s", exc)
        raise OcrEngineUnavailableError("OCR 识别失败") from exc

    lines: list[str] = []
    # 兼容旧版 [[[box, (text, score)], ...]] 与部分新版结构
    pages = result or []
    for page in pages:
        if not page:
            continue
        if isinstance(page, dict):
            texts = page.get("rec_texts") or page.get("texts") or []
            for text in texts:
                cleaned = str(text or "").strip()
                if cleaned:
                    lines.append(cleaned)
            continue
        for item in page:
            if not item:
                continue
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                payload = item[1]
                if isinstance(payload, (list, tuple)) and payload:
                    cleaned = str(payload[0] or "").strip()
                else:
                    cleaned = str(payload or "").strip()
                if cleaned:
                    lines.append(cleaned)
    return "\n".join(lines).strip()
