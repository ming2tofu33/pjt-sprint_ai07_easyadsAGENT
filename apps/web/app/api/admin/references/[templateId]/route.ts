import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../../../_proxy/orchestrator";
import { adminReferenceUpdateSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";

export function PATCH(request: NextRequest, { params }: { params: { templateId: string } }) {
  return proxyOrchestratorJson(
    request,
    "PATCH",
    `/api/v1/admin/references/${encodeURIComponent(params.templateId)}`,
    undefined,
    { requireNonGuestUser: true, bodySchema: adminReferenceUpdateSchema }
  );
}
