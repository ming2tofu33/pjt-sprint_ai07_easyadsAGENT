import { NextRequest } from "next/server";

import { proxyOrchestratorBinary } from "../../../../_proxy/orchestrator";

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, { params }: { params: { removalGroup: string; filename: string } }) {
  return proxyOrchestratorBinary(
    request,
    `/api/v1/references/temp-assets/${encodeURIComponent(params.removalGroup)}/${encodeURIComponent(params.filename)}`,
    "public, max-age=604800, immutable"
  );
}
