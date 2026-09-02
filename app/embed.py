def load_model() -> None:
    """Load BAAI/bge-m3 once at application startup."""
    raise NotImplementedError


def is_loaded() -> bool:
    """Return whether the embedding model is ready."""
    raise NotImplementedError


def encode_documents(texts: list[str]) -> list[list[float]]:
    """Encode document chunks into normalized 1024-dim dense vectors."""
    raise NotImplementedError


def encode_query(question: str) -> list[float]:
    """Encode a user question into a normalized 1024-dim dense vector."""
    raise NotImplementedError
