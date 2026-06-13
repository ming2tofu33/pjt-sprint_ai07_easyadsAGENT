import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/state`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
