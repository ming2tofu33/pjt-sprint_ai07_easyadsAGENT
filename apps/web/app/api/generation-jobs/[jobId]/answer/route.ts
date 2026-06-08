import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { jobId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/generation-jobs/${encodeURIComponent(params.jobId)}/answer`,
    undefined,
    { injectVerifiedUserId: true }
  );
}
