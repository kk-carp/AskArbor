from datetime import datetime
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
    conversation_id: UUID | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    id: str
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


class OwnerInfo(BaseModel):
    """员工未命中时的负责人；configured=false 表示未配置，不编造联系方式。"""

    configured: bool
    topic_key: str | None = None
    topic_name: str | None = None
    name: str | None = None
    contact: str | None = None


class AskResponse(BaseModel):
    answer: str
    hit: bool
    sources: list[SourceItem]
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    owner: OwnerInfo | None = None


class ConversationItem(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageItem(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1)
    conversation_id: UUID | None = None


class ReplyTicketRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply: str = Field(min_length=1)


class TicketResponse(BaseModel):
    id: UUID
    question: str
    student_id: str
    assignee_id: str
    status: str
    reply: str | None = None
    conversation_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TopicOwnerUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_key: str = Field(min_length=1, max_length=64)
    topic_name: str = Field(min_length=1, max_length=128)
    keywords: str = ""
    name: str = Field(min_length=1, max_length=64)
    contact: str = Field(min_length=1, max_length=255)


class TopicOwnerResponse(BaseModel):
    topic_key: str
    topic_name: str
    keywords: str
    name: str
    contact: str


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
