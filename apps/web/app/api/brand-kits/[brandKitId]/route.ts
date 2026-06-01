import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { brandKitId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/brand-kits/${encodeURIComponent(params.brandKitId)}`);
}

export function PATCH(request: NextRequest, { params }: { params: { brandKitId: string } }) {
  return proxyOrchestratorJson(request, "PATCH", `/api/v1/brand-kits/${encodeURIComponent(params.brandKitId)}`);
}
