import { requestJson } from "@/api/http";
import type { AskResponse, ConversationItem, MessageItem } from "@/types";

export function listConversations(): Promise<ConversationItem[]> {
  return requestJson<ConversationItem[]>("/conversations");
}

export function listMessages(conversationId: string): Promise<MessageItem[]> {
  return requestJson<MessageItem[]>(`/conversations/${conversationId}/messages`);
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
