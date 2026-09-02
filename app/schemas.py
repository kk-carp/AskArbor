from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Role(str, Enum):
    student = "student"
    employee = "employee"
    teaching = "teaching"


class SpaceId(str, Enum):
    student = "student"
    company = "company"


class AskRequest(BaseModel):
    role: Role
    question: str = Field(min_length=1)


class SourceItem(BaseModel):
    document_id: UUID
    title: str
    space_id: str


class AskResponse(BaseModel):
    answer: str
    hit: bool
    sources: list[SourceItem]


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    space_id: str
    status: str
    chunk_count: int


class HealthResponse(BaseModel):
    api: bool
    database: bool
    embedding_loaded: bool
