import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(request, "GET", `/api/v1/assets/${encodeURIComponent(params.assetId)}`, undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
