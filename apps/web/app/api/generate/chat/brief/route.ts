import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { chatBriefSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/marketing/chat/brief", undefined, {
    bodySchema: chatBriefSchema
  });
}
