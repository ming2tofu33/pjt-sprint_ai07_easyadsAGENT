import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../_proxy/orchestrator";
import { adminReferenceSchema } from "../../_schemas/generate";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/admin/references", undefined, {
    requireNonGuestUser: true
  });
}

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/admin/references", undefined, {
    requireNonGuestUser: true,
    bodySchema: adminReferenceSchema,
    injectVerifiedUserIdQuery: { userKey: "user_id" }
  });
}
