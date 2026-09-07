import { requestJson } from "@/api/http";
import type { LearningPathResponse } from "@/types";

export function fetchLearningPath(): Promise<LearningPathResponse> {
  return requestJson<LearningPathResponse>("/learning-path");
}
