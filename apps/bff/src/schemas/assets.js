import { z } from "zod";

export const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"];
export const assetPresignSchema = z.object({
  kind: z.enum(["upload", "source", "reference"]), filename: z.string().trim().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes), sizeBytes: z.number().int().positive(),
  workspaceId: z.string().trim().min(1).optional(), threadId: z.string().trim().min(1).optional()
});
