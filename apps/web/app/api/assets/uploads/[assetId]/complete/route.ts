import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { assetId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/assets/uploads/${encodeURIComponent(params.assetId)}/complete`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}
