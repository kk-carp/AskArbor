import { requestJson } from "@/api/http";
import type { TopicOwnerItem, TopicOwnerUpsertPayload } from "@/types";

export function listTopicOwners(): Promise<TopicOwnerItem[]> {
  return requestJson<TopicOwnerItem[]>("/topic_owners");
}

export function upsertTopicOwner(payload: TopicOwnerUpsertPayload): Promise<TopicOwnerItem> {
  return requestJson<TopicOwnerItem>("/topic_owners", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
