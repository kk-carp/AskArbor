import { requestJson } from "@/api/http";
import type { MetricsSnapshot } from "@/types";

export function fetchMetrics(): Promise<MetricsSnapshot> {
  return requestJson<MetricsSnapshot>("/metrics");
}
