import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { chatStartSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/v1/marketing/chat/start", undefined, {
    bodySchema: chatStartSchema
  });
}
