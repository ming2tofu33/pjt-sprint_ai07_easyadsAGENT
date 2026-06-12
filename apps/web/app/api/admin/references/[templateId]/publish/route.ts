import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/admin/references/${encodeURIComponent(params.templateId)}/publish`,
    undefined,
    { requireNonGuestUser: true }
  );
}
