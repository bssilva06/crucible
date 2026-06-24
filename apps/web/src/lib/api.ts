import type { RunCreateRequest, RunResponse } from "@/lib/types";

export async function createRun(apiBaseUrl: string, request: RunCreateRequest): Promise<RunResponse> {
  const response = await fetch(`${apiBaseUrl}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.detail || "Run request failed";
    throw new Error(String(message));
  }
  return payload as RunResponse;
}
