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
    """Search ready chunks, filtering spaces in SQL before vector ranking.

    The WHERE clause must include `chunks.space_id = ANY(:allowed_spaces)`
    and `documents.status = 'ready'`. Do not rank the full corpus in Python.
    """
    raise NotImplementedError
