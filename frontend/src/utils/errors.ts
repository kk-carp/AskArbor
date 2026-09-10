import { ApiError } from "@/types";

export interface DuplicateDocumentInfo {
  existingId: string;
  existingTitle: string;
  spaceId: string;
}

function readDetailObject(error: ApiError): Record<string, unknown> | null {
  const payload = error.body;
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return null;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail !== "object" || detail === null) {
    return null;
  }
  return detail as Record<string, unknown>;
}

/** 同空间相同内容；409 不是知识库未命中。 */
export function duplicateDocumentInfo(error: unknown): DuplicateDocumentInfo | null {
  if (!(error instanceof ApiError) || error.status !== 409) {
    return null;
  }
  const detail = readDetailObject(error);
  if (detail?.code !== "duplicate_document") {
    return null;
  }
  const existingId = typeof detail.existing_id === "string" ? detail.existing_id : "";
  const existingTitle = typeof detail.existing_title === "string" ? detail.existing_title : "";
  const spaceId = typeof detail.space_id === "string" ? detail.space_id : "";
  if (!existingId) {
    return null;
  }
  return { existingId, existingTitle, spaceId };
}

/** 把系统故障与知识库未命中区分开，禁止用拒答文案覆盖 502/503 */
export function describeRequestError(error: unknown): { title: string; detail: string } {
  if (error instanceof ApiError) {
    if (error.status === 502) {
      return {
        title: "上游服务失败",
        detail: error.detail || "大模型暂时不可用，请稍后重试。这不是知识库未命中。",
      };
    }
    if (error.status === 503) {
      return {
        title: "服务未就绪",
        detail: error.detail || "数据库或向量模型未加载，请稍后重试。这不是知识库未命中。",
      };
    }
    if (error.status === 429) {
      return {
        title: "请求过于频繁",
        detail: error.detail || "请稍后再试。这不是知识库未命中。",
      };
    }
    if (error.status === 409) {
      return { title: "文档重复", detail: error.detail || "该空间已有相同内容的文档" };
    }
    if (error.status === 413) {
      return { title: "文件过大", detail: error.detail };
    }
    if (error.status === 403) {
      return { title: "没有权限", detail: error.detail };
    }
    if (error.status === 400) {
      return { title: "请求无效", detail: error.detail };
    }
    if (error.status === 401) {
      return { title: "未登录或登录已失效", detail: error.detail };
    }
    return { title: `请求失败（${error.status}）`, detail: error.detail };
  }
  if (error instanceof DOMException && error.name === "TimeoutError") {
    return { title: "请求超时", detail: "服务响应超时，请稍后重试。" };
  }
  if (error instanceof Error) {
    return { title: "请求失败", detail: error.message };
  }
  return { title: "请求失败", detail: "未知错误" };
}
