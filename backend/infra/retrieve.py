from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from backend import db
from backend.errors import ServiceUnavailableError


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
    """SQL 中先按空间过滤，再做向量排序。"""
    if not allowed_spaces:
        return []
    if top_k <= 0:
        return []
    if not query_vector:
        raise ValueError("query_vector 不能为空")

    db.init_engine()
    if db.SessionLocal is None:
        raise ServiceUnavailableError("数据库会话未初始化")

    vector_literal = "[" + ",".join(f"{value:.10f}" for value in query_vector) + "]"
    spaces_literal = "{" + ",".join(allowed_spaces) + "}"

    sql = text(
        """
        SELECT
            chunks.content AS content,
            1 - (chunks.embedding <=> CAST(:query_vector AS vector)) AS score,
            documents.id AS document_id,
            documents.title AS title,
            chunks.space_id AS space_id
        FROM chunks
        JOIN documents ON documents.id = chunks.document_id
        WHERE chunks.space_id = ANY(CAST(:allowed_spaces AS text[]))
          AND documents.status = 'ready'
        ORDER BY chunks.embedding <=> CAST(:query_vector AS vector)
        LIMIT :top_k
        """
    )
    # 仅 ready 可检索：failed/offline/processing 均被排除，勿在 Python 层再过滤全量结果

    with db.SessionLocal() as session:
        rows = session.execute(
            sql,
            {
                "query_vector": vector_literal,
                "allowed_spaces": spaces_literal,
                "top_k": top_k,
            },
        ).mappings()
        return [
            RetrievedChunk(
                content=row["content"],
                score=float(row["score"]),
                document_id=UUID(str(row["document_id"])),
                title=row["title"],
                space_id=row["space_id"],
            )
            for row in rows
        ]
