import { requestJson } from "@/api/http";
import type { AdvancedResourcesPlanResponse, AdvancedResourcesToolsResponse } from "@/types";

export function fetchAdvancedResourceTools(): Promise<AdvancedResourcesToolsResponse> {
  return requestJson<AdvancedResourcesToolsResponse>("/advanced-resources/tools");
}

export function planAdvancedResources(
  weakPoints?: string[],
): Promise<AdvancedResourcesPlanResponse> {
  return requestJson<AdvancedResourcesPlanResponse>("/advanced-resources/plan", {
    method: "POST",
    body: JSON.stringify(weakPoints?.length ? { weak_points: weakPoints } : {}),
  });
}
