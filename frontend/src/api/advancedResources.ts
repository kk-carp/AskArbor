import { ApiError } from "@/types";
import type {
  AdvancedResourcesPlanResponse,
  AdvancedResourcesToolsResponse,
  AdvancedResourceStep,
} from "@/types";
import { requestJson } from "@/api/http";

export function fetchAdvancedResourceTools(): Promise<AdvancedResourcesToolsResponse> {
  return requestJson<AdvancedResourcesToolsResponse>("/advanced-resources/tools");
}

export function planAdvancedResources(
  options: { weakPoints?: string[]; refresh?: boolean } = {},
): Promise<AdvancedResourcesPlanResponse> {
  return requestJson<AdvancedResourcesPlanResponse>("/advanced-resources/plan", {
    method: "POST",
    body: JSON.stringify({
      ...(options.weakPoints?.length ? { weak_points: options.weakPoints } : {}),
      refresh: Boolean(options.refresh),
    }),
  });
}

export type PlanStreamHandlers = {
  onStep?: (step: AdvancedResourceStep) => void;
  onFinal?: (payload: AdvancedResourcesPlanResponse) => void;
  onError?: (payload: { status?: number; detail?: string }) => void;
  signal?: AbortSignal;
};

function dispatchSseEvent(
  eventName: string,
  rawData: string,
  handlers: PlanStreamHandlers,
): void {
  if (!rawData.trim()) return;
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawData);
  } catch {
    return;
  }
  if (eventName === "step" && parsed && typeof parsed === "object") {
    handlers.onStep?.(parsed as AdvancedResourceStep);
  } else if (eventName === "final" && parsed && typeof parsed === "object") {
    handlers.onFinal?.(parsed as AdvancedResourcesPlanResponse);
  } else if (eventName === "error" && parsed && typeof parsed === "object") {
    handlers.onError?.(parsed as { status?: number; detail?: string });
  }
}

/** POST /advanced-resources/plan/stream — SSE：step / final / error / done */
export async function planAdvancedResourcesStream(
  handlers: PlanStreamHandlers,
  options: { weakPoints?: string[]; refresh?: boolean } = {},
): Promise<void> {
  const response = await fetch("/advanced-resources/plan/stream", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      ...(options.weakPoints?.length ? { weak_points: options.weakPoints } : {}),
      refresh: Boolean(options.refresh),
    }),
    signal: handlers.signal ?? AbortSignal.timeout(180_000),
  });

  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new ApiError(500, "流式响应为空");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";
  let dataLines: string[] = [];

  const flush = () => {
    dispatchSseEvent(eventName, dataLines.join("\n"), handlers);
    eventName = "message";
    dataLines = [];
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let newline = buffer.indexOf("\n");
    while (newline >= 0) {
      let line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);

      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim() || "message";
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart());
      } else if (line === "") {
        flush();
      }
      newline = buffer.indexOf("\n");
    }
  }
  if (dataLines.length) flush();
}
