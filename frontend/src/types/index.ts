/** 登录身份：学员 / 内部员工 / 教学岗 */
export type UserRole = "student" | "employee" | "teaching";

/** 知识空间：课程空间 / 内部空间 */
export type SpaceId = "student" | "company";

/** 文档入库状态 */
export type DocumentStatus = "processing" | "ready" | "failed" | "offline";

/** 工单状态 */
export type TicketStatus = "open" | "replied";

/** 当前登录用户（对应 GET /me，权限展示的唯一来源） */
export interface MeResponse {
  id: string;
  username: string;
  role: UserRole;
  is_teaching: boolean;
  allowed_spaces: SpaceId[];
  advisor_id: string | null;
  can_manage_documents: boolean;
}

/** 问答来源：只渲染接口返回字段，不解析模型正文 */
export interface SourceItem {
  document_id: string;
  title: string;
  space_id: SpaceId;
  path?: string | null;
  /** 向量相似度（越高越相关）；旧响应可能缺省 */
  score?: number | null;
}

/** 员工未命中时的主题负责人 */
export interface OwnerInfo {
  configured: boolean;
  topic_key: string | null;
  topic_name: string | null;
  name: string | null;
  contact: string | null;
}

/** POST /ask 或 /ocr 响应；ocr_failed 时 hit 为 null */
export interface AskResponse {
  answer: string;
  hit: boolean | null;
  sources: SourceItem[];
  conversation_id: string | null;
  ticket_id: string | null;
  owner: OwnerInfo | null;
  error_type?: "ocr_failed" | "screenshot_only" | null;
  extracted_text?: string | null;
  extract_method?: "vision" | "ocr" | null;
}

/** GET /conversations 列表项 */
export interface ConversationItem {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

/** GET /conversations/{id}/messages 列表项（不含 hit） */
export interface MessageItem {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

/**
 * 当次 /ask 的命中元数据。
 * 后端消息接口不落库 hit / ticket_id / owner，由前端按消息 id 缓存。
 */
export interface MessageAskMeta {
  hit: boolean | null;
  ticket_id: string | null;
  owner: OwnerInfo | null;
  sources: SourceItem[];
  error_type?: "ocr_failed" | "screenshot_only" | null;
}

/** GET /documents */
export interface DocumentItem {
  id: string;
  title: string;
  space_id: SpaceId;
  status: DocumentStatus;
  chunk_count: number;
  error: string | null;
  path?: string | null;
}

/** POST /code-ingest */
export interface SkippedCodeFile {
  path: string;
  reason: string;
}

export interface CodeIngestResponse {
  space_id: SpaceId;
  documents: DocumentItem[];
  skipped: SkippedCodeFile[];
}

/** GET /tickets */
export interface TicketItem {
  id: string;
  question: string;
  student_id: string;
  assignee_id: string;
  status: TicketStatus;
  reply: string | null;
  conversation_id: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /topic_owners */
export interface TopicOwnerItem {
  topic_key: string;
  topic_name: string;
  keywords: string;
  name: string;
  contact: string;
}

export interface TopicOwnerUpsertPayload {
  topic_key: string;
  topic_name: string;
  keywords: string;
  name: string;
  contact: string;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export type ExternalKind = "paper" | "docs" | "oss";

export interface CourseRecommendation {
  document_id: string;
  title: string;
  space_id: SpaceId;
  path?: string | null;
}

export interface ExternalRecommendation {
  title: string;
  url: string;
  host: string;
  kind: ExternalKind;
  snippet: string;
}

/** GET /learning-path：无 hit，搜索失败用 error_type；默认读缓存 */
export interface LearningPathResponse {
  weak_points: string[];
  course: CourseRecommendation[];
  external: ExternalRecommendation[];
  error_type: "search_unavailable" | "search_timeout" | null;
  message: string | null;
  from_cache: boolean;
}

/** 业务错误：与 V1 的 400/401/403/413/502/503 语义对齐 */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}
