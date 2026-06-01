import { NextRequest, NextResponse } from "next/server";

const ORCHESTRATOR_BASE_URL = process.env.ORCHESTRATOR_BASE_URL || "http://localhost:8000";

type ProxyMethod = "GET" | "POST" | "PATCH";

function buildTargetUrl(path: string, request: NextRequest): string {
  const target = new URL(path, ORCHESTRATOR_BASE_URL);
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value);
  });
  return target.toString();
}

export async function proxyOrchestratorJson(request: NextRequest, method: ProxyMethod, path: string) {
  const init: RequestInit = {
    method,
    headers: { "content-type": "application/json" },
    cache: "no-store"
  };

  if (method !== "GET") {
    const body = await request.text();
    if (body) {
      init.body = body;
    }
  }

  try {
    const response = await fetch(buildTargetUrl(path, request), init);
    const payload = await response.json().catch(() => ({}));
    return NextResponse.json(payload, { status: response.status });
  } catch {
    return NextResponse.json(
      {
        success: false,
        error_code: "orchestrator_unavailable",
        message: "Orchestrator API is unavailable.",
        detail: "Failed to reach the orchestrator backend from the BFF proxy."
      },
      { status: 502 }
    );
  }
}
