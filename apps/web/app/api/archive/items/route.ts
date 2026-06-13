import { NextRequest } from "next/server";

import { archiveItemCreateSchema } from "../../_schemas/archive";
import { proxyOrchestratorJson } from "../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

function compactObject(value: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== null));
}

function toArchiveItemPayload(body: unknown) {
  const data = body && typeof body === "object" && !Array.isArray(body) ? (body as Record<string, unknown>) : {};
  return compactObject({
    title: data.title,
    public_job_id: data.public_job_id ?? data.publicJobId,
    image_url: data.image_url ?? data.imageUrl,
    thumbnail_url: data.thumbnail_url ?? data.thumbnailUrl,
    status: data.status,
    ad_format: data.ad_format ?? data.adFormat,
    platform: data.platform,
    source: data.source,
    workspace_id: data.workspace_id ?? data.workspaceId,
    user_id: data.user_id ?? data.userId,
    account_type: data.account_type ?? data.accountType,
    metadata: data.metadata
  });
}

export function GET(request: NextRequest) {
  return proxyOrchestratorJson(request, "GET", "/api/v1/archive/items", undefined, {
    injectVerifiedUserIdQuery: { userKey: "user_id", accountKey: "account_type" }
  });
}

export function POST(request: NextRequest) {
  return proxyOrchestratorJson(request, "POST", "/api/v1/archive/items", toArchiveItemPayload, {
    bodySchema: archiveItemCreateSchema,
    injectVerifiedUserIdSnakeBody: true,
    successStatus: 201
  });
}
