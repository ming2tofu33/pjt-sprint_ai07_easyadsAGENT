import { NextRequest } from "next/server";

import { archiveItemUpdateSchema } from "../../../_schemas/archive";
import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(
    request,
    "GET",
    `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}

export function PATCH(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(
    request,
    "PATCH",
    `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`,
    undefined,
    { bodySchema: archiveItemUpdateSchema, injectVerifiedUserIdSnakeBody: true }
  );
}

export function DELETE(request: NextRequest, { params }: { params: { archiveItemId: string } }) {
  return proxyOrchestratorJson(
    request,
    "DELETE",
    `/api/v1/archive/items/${encodeURIComponent(params.archiveItemId)}`,
    undefined,
    { injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" } }
  );
}
