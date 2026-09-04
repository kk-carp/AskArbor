import { requestJson } from "@/api/http";
import type { LoginPayload, MeResponse } from "@/types";

export function login(payload: LoginPayload): Promise<MeResponse> {
  return requestJson<MeResponse>("/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/logout", { method: "POST" });
}

export function fetchMe(): Promise<MeResponse> {
  return requestJson<MeResponse>("/me");
}
