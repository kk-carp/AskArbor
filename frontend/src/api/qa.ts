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
  const body: { question: string; conversation_id?: string } = { question };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  return requestJson<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
