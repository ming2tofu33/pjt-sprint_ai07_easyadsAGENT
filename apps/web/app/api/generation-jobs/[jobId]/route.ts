import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { jobId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/generation-jobs/${encodeURIComponent(params.jobId)}`,
    undefined,
    { injectVerifiedUserIdHeader: true }
  );
}
