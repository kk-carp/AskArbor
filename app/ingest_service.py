from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile


@dataclass(frozen=True)
class DocumentResult:
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int


def ingest_document(file: UploadFile, space_id: str) -> DocumentResult:
    """编排上传 → 解析 → 切片 → 向量化 → 持久化流程。

    顺序：校验空间、保存文件、写入 documents(processing)、解析、
    切片、编码、写入 chunks、更新 documents(ready)。
    若出现可预期失败，应回滚切片写入、标记文档 failed，且不泄露敏感信息。
    """
    raise NotImplementedError
