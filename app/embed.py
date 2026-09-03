from __future__ import annotations

from threading import Lock
from typing import Any

from app.config import settings
from app.errors import ServiceUnavailableError

_model_lock = Lock()
_model: Any | None = None


def load_model() -> None:
    """在应用启动时加载一次 BAAI/bge-m3 模型。"""
    global _model

    if _model is not None:
        return

    with _model_lock:
        if _model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embed_model)
        except Exception as exc:  # pragma: no cover - 依赖真实模型环境
            raise ServiceUnavailableError("向量模型加载失败") from exc


def is_loaded() -> bool:
    """返回向量模型是否已就绪。"""
    return _model is not None


def _ensure_model() -> Any:
    if _model is None:
        raise ServiceUnavailableError("向量模型未加载")
    return _model


def _normalize_vectors(vectors: list[list[float]]) -> list[list[float]]:
    normalized: list[list[float]] = []
    for vector in vectors:
        norm = sum(item * item for item in vector) ** 0.5
        if norm == 0:
            normalized.append(vector)
            continue
        normalized.append([item / norm for item in vector])
    return normalized


def encode_documents(texts: list[str]) -> list[list[float]]:
    """将文档切片编码为归一化的 1024 维 dense 向量。"""
    if not texts:
        return []

    model = _ensure_model()
    try:
        embeddings = model.encode(
            texts,
            batch_size=settings.embed_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except TypeError:
        # 兼容少量旧接口，不支持 normalize_embeddings 参数时走手动归一化。
        embeddings = model.encode(
            texts,
            batch_size=settings.embed_batch_size,
            convert_to_numpy=True,
        )
        return _normalize_vectors(embeddings.tolist())
    except Exception as exc:  # pragma: no cover - 依赖真实模型环境
        raise ServiceUnavailableError("文档向量编码失败") from exc

    vectors = embeddings.tolist()
    if settings.embedding_dim and vectors and len(vectors[0]) != settings.embedding_dim:
        raise ServiceUnavailableError("向量维度与配置不一致")
    return vectors


def encode_query(question: str) -> list[float]:
    """将用户问题编码为归一化的 1024 维 dense 向量。"""
    text = question.strip()
    if not text:
        raise ValueError("问题不能为空")

    vectors = encode_documents([text])
    if not vectors:
        raise ServiceUnavailableError("问题向量编码失败")
    return vectors[0]
