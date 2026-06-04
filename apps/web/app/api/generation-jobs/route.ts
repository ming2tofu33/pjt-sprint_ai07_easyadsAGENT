import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", (body) => {
    const payload = { ...(body as Record<string, unknown>) };
    payload.selected_reference_template_id = payload.selected_reference_template_id ?? payload.selectedReferenceTemplateId;
    delete payload.selectedReferenceTemplateId;
    return payload;
  });
}
