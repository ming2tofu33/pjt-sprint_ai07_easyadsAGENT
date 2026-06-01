import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/brand-kits");
}
