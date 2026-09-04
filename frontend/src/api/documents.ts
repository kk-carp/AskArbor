import { requestJson } from "@/api/http";
import type { DocumentItem, SpaceId } from "@/types";

export function listDocuments(): Promise<DocumentItem[]> {
  return requestJson<DocumentItem[]>("/documents");
}

export function uploadDocument(space: SpaceId, file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("space", space);
  form.append("file", file);
  return requestJson<DocumentItem>("/documents", {
    method: "POST",
    body: form,
  });
}

export function offlineDocument(documentId: string): Promise<DocumentItem> {
  return requestJson<DocumentItem>(`/documents/${documentId}/offline`, {
    method: "POST",
  });
}
