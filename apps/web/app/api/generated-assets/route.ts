import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";

const PROJECT_ROOT = path.resolve(process.cwd(), "../..");
const OUTPUTS_ROOT = path.resolve(PROJECT_ROOT, "data", "outputs");

const CONTENT_TYPE_BY_EXT: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp"
};

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const requestedPath = request.nextUrl.searchParams.get("path");
  if (!requestedPath) {
    return NextResponse.json({ error: "missing_path" }, { status: 400 });
  }

  const normalizedPath = requestedPath.replace(/\\/g, "/");
  if (!normalizedPath.startsWith("data/outputs/") || normalizedPath.includes("..")) {
    return NextResponse.json({ error: "invalid_path" }, { status: 400 });
  }

  const absolutePath = path.resolve(PROJECT_ROOT, normalizedPath);
  if (!absolutePath.startsWith(`${OUTPUTS_ROOT}${path.sep}`)) {
    return NextResponse.json({ error: "invalid_path" }, { status: 400 });
  }

  try {
    const fileStat = await stat(absolutePath);
    if (!fileStat.isFile()) {
      return NextResponse.json({ error: "not_found" }, { status: 404 });
    }

    const file = await readFile(absolutePath);
    const contentType = CONTENT_TYPE_BY_EXT[path.extname(absolutePath).toLowerCase()] ?? "application/octet-stream";

    return new NextResponse(new Uint8Array(file), {
      headers: {
        "cache-control": "public, max-age=31536000, immutable",
        "content-length": String(file.length),
        "content-type": contentType
      }
    });
  } catch {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
}
