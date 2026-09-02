from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RetrievedChunk:
    content: str
    score: float
    document_id: UUID
    title: str
    space_id: str


def search_chunks(
    query_vector: list[float],
    allowed_spaces: list[str],
    top_k: int,
) -> list[RetrievedChunk]:
    """检索 ready 状态切片，并在 SQL 中先按空间过滤再做向量排序。

    WHERE 子句必须包含 `chunks.space_id = ANY(:allowed_spaces)` 与
    `documents.status = 'ready'`，禁止在 Python 层对全量排序结果再过滤。
    """
    raise NotImplementedError
