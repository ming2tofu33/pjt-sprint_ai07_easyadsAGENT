import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/references");
}
