from datetime import datetime
from enum import Enum
from typing import Any
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
    position_key: str | None = None


class SourceItem(BaseModel):
    document_id: UUID
    title: str
    space_id: str
    path: str | None = None
    score: float | None = None


class OwnerInfo(BaseModel):
    """员工未命中时的负责人；configured=false 表示未配置，不编造联系方式。"""

    configured: bool
    topic_key: str | None = None
    topic_name: str | None = None
    name: str | None = None
    contact: str | None = None


class AskResponse(BaseModel):
    answer: str
    hit: bool | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    conversation_id: UUID | None = None
    ticket_id: UUID | None = None
    owner: OwnerInfo | None = None
    error_type: str | None = None
    extracted_text: str | None = None
    extract_method: str | None = None


class ConversationItem(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    message_count: int
    preview: str


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
    path: str | None = None


class SkippedCodeFile(BaseModel):
    path: str
    reason: str


class CodeIngestResponse(BaseModel):
    space_id: str
    documents: list[DocumentResponse]
    skipped: list[SkippedCodeFile]


class CourseRecommendation(BaseModel):
    document_id: UUID
    title: str
    space_id: str
    path: str | None = None


class ExternalRecommendation(BaseModel):
    title: str
    url: str
    host: str
    kind: str
    snippet: str = ""


class LearningPathResponse(BaseModel):
    weak_points: list[str]
    course: list[CourseRecommendation]
    external: list[ExternalRecommendation]
    error_type: str | None = None
    message: str | None = None
    from_cache: bool = False


class AdvancedResourceToolSpec(BaseModel):
    name: str
    description: str
    params: list[str] = []


class AdvancedResourcesToolsResponse(BaseModel):
    tools: list[AdvancedResourceToolSpec]


class AdvancedResourcesRunRequest(BaseModel):
    tool: str
    args: dict[str, Any] | None = None


class AdvancedResourcesRunResponse(BaseModel):
    tool: str
    ok: bool
    data: dict[str, Any] = {}
    error_type: str | None = None
    message: str | None = None


class AdvancedResourcesPlanRequest(BaseModel):
    weak_points: list[str] | None = None


class AdvancedResourceStep(BaseModel):
    tool: str
    ok: bool
    data: dict[str, Any] = {}
    error_type: str | None = None
    message: str | None = None


class AdvancedResourcesWeakPointDetail(BaseModel):
    topic: str
    why: str = ""


class AdvancedResourcesMaterialItem(BaseModel):
    ref_id: str
    channel: str | None = None
    title: str | None = None
    path: str | None = None
    url: str | None = None
    host: str | None = None
    kind: str | None = None
    reason: str = ""
    how_to_use: str = ""


class AdvancedResourcesReport(BaseModel):
    title: str
    capability_analysis: str = ""
    weak_points_detail: list[AdvancedResourcesWeakPointDetail] = []
    materials: list[AdvancedResourcesMaterialItem] = []
    next_steps: list[str] = []


class AdvancedResourcesPlanResponse(BaseModel):
    weak_points: list[str]
    course: list[CourseRecommendation]
    external: list[ExternalRecommendation]
    steps: list[AdvancedResourceStep] = []
    error_type: str | None = None
    message: str | None = None
    report: AdvancedResourcesReport | None = None


class HealthResponse(BaseModel):
    api: bool
    database: bool
    embedding_loaded: bool
