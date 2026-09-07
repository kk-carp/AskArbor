import { requestJson } from "@/api/http";
import type { LearningPathResponse } from "@/types";

export function fetchLearningPath(refresh = false): Promise<LearningPathResponse> {
  const query = refresh ? "?refresh=true" : "";
  return requestJson<LearningPathResponse>(`/learning-path${query}`);
}
