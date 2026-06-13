import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest, { params }: { params: { threadId: string } }) {
  return proxyOrchestratorJson(
    request,
    "POST",
    `/api/v1/chat-threads/${encodeURIComponent(params.threadId)}/archive`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "userId", accountKey: "accountType" } }
  );
}
