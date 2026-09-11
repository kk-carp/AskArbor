import { requestJson } from "@/api/http";
import type { TicketItem } from "@/types";

export function listTickets(): Promise<TicketItem[]> {
  return requestJson<TicketItem[]>("/tickets");
}

export function createTicket(question: string, conversationId?: string | null): Promise<TicketItem> {
  const body: { question: string; conversation_id?: string } = { question };
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  return requestJson<TicketItem>("/tickets", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function replyTicket(ticketId: string, reply: string): Promise<TicketItem> {
  return requestJson<TicketItem>(`/tickets/${ticketId}/reply`, {
    method: "POST",
    body: JSON.stringify({ reply }),
  });
}

export function deleteTicket(ticketId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/tickets/${ticketId}`, {
    method: "DELETE",
  });
}
