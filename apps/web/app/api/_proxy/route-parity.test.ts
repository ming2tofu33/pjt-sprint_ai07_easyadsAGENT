import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";

const REQUIRED_NEXT_API_ROUTES = [
  "account/delete",
  "brand-kits",
  "brand-kits/current",
  "brand-kits/[brandKitId]",
  "generated-assets",
  "generation-jobs",
  "generation-jobs/[jobId]",
  "generation-jobs/[jobId]/answer",
  "references",
  "references/[templateId]",
  "references/[templateId]/similar",
  "generate/chat/start",
  "generate/chat/brief",
  "generate/chat/answer",
  "generate/photo/upload",
  "generate/photo/start",
  "assets/uploads/presign",
  "assets/uploads/[assetId]/complete",
  "assets/[assetId]",
  "chat-threads",
  "chat-threads/[threadId]",
  "chat-threads/[threadId]/messages",
  "chat-threads/[threadId]/state",
  "chat-threads/[threadId]/archive",
  "archive/items",
  "archive/items/[archiveItemId]",
  "admin/references",
  "admin/references/[templateId]",
  "admin/references/[templateId]/publish",
  "admin/references/[templateId]/unpublish",
  "references/temp-assets/[removalGroup]/[filename]"
] as const;

const API_ROOT = path.resolve(process.cwd(), "app", "api");

describe("Next BFF route parity", () => {
  it.each(REQUIRED_NEXT_API_ROUTES)("has a route handler for /api/%s", (routePath) => {
    const filePath = path.join(API_ROOT, routePath, "route.ts");
    expect(fs.existsSync(filePath), `missing Next route handler: ${filePath}`).toBe(true);
  });
});
