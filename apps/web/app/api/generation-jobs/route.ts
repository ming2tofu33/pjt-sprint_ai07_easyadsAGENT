import { NextRequest } from "next/server";

import { proxyOrchestratorJson } from "../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/generation-jobs", (body) => {
    const payload = { ...(body as Record<string, unknown>) };
    payload.selected_reference_template_id = payload.selected_reference_template_id ?? payload.selectedReferenceTemplateId;
    payload.selected_copy_id = payload.selected_copy_id ?? payload.selectedCopyId;
    payload.selected_channel_id = payload.selected_channel_id ?? payload.selectedChannelId;
    payload.selected_tone = payload.selected_tone ?? payload.selectedTone;
    payload.custom_direction = payload.custom_direction ?? payload.customDirection;
    payload.user_custom_headline = payload.user_custom_headline ?? payload.userCustomHeadline;
    payload.user_custom_subcopy = payload.user_custom_subcopy ?? payload.userCustomSubcopy;
    payload.source_image_path = payload.source_image_path ?? payload.sourceImagePath;
    payload.reference_image_path = payload.reference_image_path ?? payload.referenceImagePath;
    delete payload.selectedReferenceTemplateId;
    delete payload.selectedCopyId;
    delete payload.selectedChannelId;
    delete payload.selectedTone;
    delete payload.customDirection;
    delete payload.userCustomHeadline;
    delete payload.userCustomSubcopy;
    delete payload.sourceImagePath;
    delete payload.referenceImagePath;
    return payload;
  });
}
