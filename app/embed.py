def load_model() -> None:
    """在应用启动时加载一次 BAAI/bge-m3 模型。"""
    raise NotImplementedError


def is_loaded() -> bool:
    """返回向量模型是否已就绪。"""
    raise NotImplementedError


def encode_documents(texts: list[str]) -> list[list[float]]:
    """将文档切片编码为归一化的 1024 维 dense 向量。"""
    raise NotImplementedError


def encode_query(question: str) -> list[float]:
    """将用户问题编码为归一化的 1024 维 dense 向量。"""
    raise NotImplementedError
