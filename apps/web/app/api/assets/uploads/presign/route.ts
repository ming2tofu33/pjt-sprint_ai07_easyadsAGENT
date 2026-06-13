import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { assetPresignSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/assets/uploads/presign", undefined, {
    bodySchema: assetPresignSchema,
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}
