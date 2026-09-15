import { requestJson } from "@/api/http";
import type { MemoryItem, MemoryKeysResponse } from "@/types";

export function listMemoryKeys(): Promise<MemoryKeysResponse> {
  return requestJson<MemoryKeysResponse>("/memories/keys");
}

export function listMemories(): Promise<MemoryItem[]> {
  return requestJson<MemoryItem[]>("/memories");
}

export function upsertMemory(key: string, value: string): Promise<MemoryItem> {
  return requestJson<MemoryItem>(`/memories/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
}

export function deleteMemory(key: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/memories/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
}
