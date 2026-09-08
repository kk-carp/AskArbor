import { ApiError } from "@/types";

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

/** 登录页的 401（密码错误）不得清会话、不得跳转 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

function readDetail(payload: unknown, fallback: string): string {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return fallback;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return String(item);
      })
      .join("；");
  }
  return fallback;
}

function isLoginRequest(path: string): boolean {
  return path === "/login" || path.endsWith("/login");
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isFormData && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const timeoutMs =
    path === "/ask" ||
    path === "/ocr" ||
    path === "/documents" ||
    path === "/code-ingest" ||
    path === "/learning-path" ||
    path === "/advanced-resources/plan" ||
    path === "/advanced-resources/plan/stream"
      ? 180_000
      : 30_000;
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
    signal: init.signal ?? AbortSignal.timeout(timeoutMs),
  });

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    const text = await response.text();
    payload = text ? { detail: text } : null;
  }

  if (!response.ok) {
    const detail = readDetail(payload, `请求失败（HTTP ${response.status}）`);
    if (response.status === 401 && !isLoginRequest(path)) {
      unauthorizedHandler?.();
    }
    throw new ApiError(response.status, detail);
  }

  return payload as T;
}
