import { requestJson, notifyUnauthorizedIfNeeded } from "@/api/http";
import { ApiError } from "@/types";
import type { AskResponse, ConversationItem, MessageItem, SourceItem } from "@/types";

export function listConversations(): Promise<ConversationItem[]> {
  return requestJson<ConversationItem[]>("/conversations");
}

export function listMessages(conversationId: string): Promise<MessageItem[]> {
  return requestJson<MessageItem[]>(`/conversations/${conversationId}/messages`);
}

export function deleteConversation(conversationId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

/** 请求体只有 question 与可选 conversation_id，不传 role / space_ids */
export function askQuestion(question: string, conversationId: string | null): Promise<AskResponse> {
  const text = (question ?? "").trim();
  if (!text) {
    return Promise.reject(new Error("问题不能为空"));
  }
  const body: { question: string; conversation_id?: string } = { question: text };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  return requestJson<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type AskStreamMeta = {
  hit: boolean;
  sources: SourceItem[];
  conversation_id: string | null;
};

export type AskStreamHandlers = {
  onMeta?: (payload: AskStreamMeta) => void;
  onDelta?: (text: string) => void;
  onFinal?: (payload: AskResponse) => void;
  onError?: (payload: { status?: number; detail?: string }) => void;
  signal?: AbortSignal;
};

function dispatchAskSse(
  eventName: string,
  rawData: string,
  handlers: AskStreamHandlers,
): void {
  if (!rawData.trim()) return;
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawData);
  } catch {
    return;
  }
  if (eventName === "meta" && parsed && typeof parsed === "object") {
    handlers.onMeta?.(parsed as AskStreamMeta);
  } else if (eventName === "delta" && parsed && typeof parsed === "object") {
    const text = (parsed as { text?: unknown }).text;
    if (typeof text === "string" && text) {
      handlers.onDelta?.(text);
    }
  } else if (eventName === "final" && parsed && typeof parsed === "object") {
    handlers.onFinal?.(parsed as AskResponse);
  } else if (eventName === "error" && parsed && typeof parsed === "object") {
    handlers.onError?.(parsed as { status?: number; detail?: string });
  }
}

/** POST /ask/stream — SSE：meta / delta / final / error / done */
export async function askQuestionStream(
  question: string,
  conversationId: string | null,
  handlers: AskStreamHandlers,
): Promise<void> {
  const text = (question ?? "").trim();
  if (!text) {
    throw new Error("问题不能为空");
  }
  const body: { question: string; conversation_id?: string } = { question: text };
  if (conversationId) {
    body.conversation_id = conversationId;
  }

  const response = await fetch("/ask/stream", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal: handlers.signal ?? AbortSignal.timeout(180_000),
  });

  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      /* ignore */
    }
    notifyUnauthorizedIfNeeded(response.status, "/ask/stream");
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new ApiError(500, "流式响应为空");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  let streamError: { status?: number; detail?: string } | null = null;
  const wrapped: AskStreamHandlers = {
    ...handlers,
    onError: (payload) => {
      streamError = payload;
      handlers.onError?.(payload);
    },
  };

  const flush = () => {
    dispatchAskSse(eventName, dataLines.join("\n"), wrapped);
    eventName = "message";
    dataLines = [];
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      let line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);

      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      } else if (line === "") {
        flush();
      }
      newline = buffer.indexOf("\n");
    }
  }
  if (dataLines.length) flush();
  if (streamError) {
    notifyUnauthorizedIfNeeded(streamError.status || 500, "/ask/stream");
    throw new ApiError(streamError.status || 500, streamError.detail || "问答处理失败");
  }
}

/** 上传截图识文后问答；全员可用 */
export function askWithImage(
  image: File,
  question: string | null,
  conversationId: string | null,
): Promise<AskResponse> {
  const form = new FormData();
  form.append("image", image, image.name || "upload.png");
  const text = (question ?? "").trim();
  if (text) {
    form.append("question", text);
  }
  if (conversationId) {
    form.append("conversation_id", conversationId);
  }
  return requestJson<AskResponse>("/ocr", {
    method: "POST",
    body: form,
  });
}
