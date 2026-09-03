from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    student = "student"
    employee = "employee"
    teaching = "teaching"


class SpaceId(str, Enum):
    student = "student"
    company = "company"


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    username: str
    role: str
    is_teaching: bool
    allowed_spaces: list[str]
    advisor_id: str | None = None
    can_manage_documents: bool = False


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
    error: str | None = None


class HealthResponse(BaseModel):
    api: bool
    database: bool
    embedding_loaded: bool
