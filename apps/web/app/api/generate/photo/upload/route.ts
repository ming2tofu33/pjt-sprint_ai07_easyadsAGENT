import { randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { NextRequest, NextResponse } from "next/server";

import { photoUploadSchema } from "../../../_schemas/generate";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function extensionForMimeType(mimeType: string) {
  if (mimeType === "image/jpeg") {
    return ".jpg";
  }
  if (mimeType === "image/webp") {
    return ".webp";
  }
  return ".png";
}

function decodeDataUrl(dataUrl: string, mimeType: string) {
  const prefix = `data:${mimeType};base64,`;
  if (!dataUrl.startsWith(prefix)) {
    throw new Error("dataUrl mime type does not match mimeType");
  }
  return Buffer.from(dataUrl.slice(prefix.length), "base64");
}

function defaultUploadDir() {
  return path.resolve(process.cwd(), "..", "..", "data", "uploads");
}

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

  let imageBuffer: Buffer;
  try {
    imageBuffer = decodeDataUrl(parsed.data.dataUrl, parsed.data.mimeType);
  } catch (error) {
    return NextResponse.json(
      {
        success: false,
        error: "invalid_request",
        error_code: "invalid_request",
        message: error instanceof Error ? error.message : "Invalid image data."
      },
      { status: 400 }
    );
  }

  const extension = extensionForMimeType(parsed.data.mimeType);
  const savedName = `photo_${randomUUID()}${extension}`;
  const uploadDir = process.env.BFF_UPLOAD_DIR || defaultUploadDir();
  await fs.mkdir(uploadDir, { recursive: true });
  await fs.writeFile(path.join(uploadDir, savedName), imageBuffer);

  return NextResponse.json({
    sourceImagePath: `data/uploads/${savedName}`,
    fileName: parsed.data.filename,
    mimeType: parsed.data.mimeType,
    sizeBytes: imageBuffer.length
  });
}
