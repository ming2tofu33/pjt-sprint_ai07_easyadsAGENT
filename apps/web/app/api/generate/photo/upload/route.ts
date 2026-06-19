import { NextRequest, NextResponse } from "next/server";

import { photoUploadSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "invalid_request",
        error_code: "invalid_request",
        message: "Invalid request body.",
        detail: { reason: "malformed_json", message: error instanceof Error ? error.message : "Request body must be valid JSON." }
      },
      { status: 400 }
    );
  }

  const parsed = photoUploadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      {
        success: false,
        error: "invalid_request",
        error_code: "invalid_request",
        message: "Invalid request body.",
        detail: parsed.error
      },
      { status: 400 }
    );
  }

  return NextResponse.json(
    {
      success: false,
      error: "legacy_photo_upload_not_supported",
      error_code: "legacy_photo_upload_not_supported",
      message: "Upload images through the asset presign and complete APIs."
    },
    { status: 410 }
  );
}
