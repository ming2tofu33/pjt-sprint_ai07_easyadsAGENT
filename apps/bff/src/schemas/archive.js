import { z } from "zod";

export const archiveItemSchema = z.object({
  title: z.string().trim().min(1), publicJobId: z.string().trim().min(1).optional(), public_job_id: z.string().trim().min(1).optional(),
  imageUrl: z.string().trim().min(1).optional().nullable(), image_url: z.string().trim().min(1).optional().nullable(),
  thumbnailUrl: z.string().trim().min(1).optional().nullable(), thumbnail_url: z.string().trim().min(1).optional().nullable(),
  status: z.enum(["saved", "favorite", "failed"]).optional(), adFormat: z.string().trim().min(1).optional().nullable(),
  ad_format: z.string().trim().min(1).optional().nullable(), platform: z.string().trim().min(1).optional().nullable(),
  source: z.enum(["generated", "reference_template", "uploaded"]).optional(), workspaceId: z.string().trim().min(1).optional(),
  workspace_id: z.string().trim().min(1).optional(), userId: z.string().trim().min(1).optional(), user_id: z.string().trim().min(1).optional(),
  metadata: z.record(z.unknown()).optional()
});
export const archiveItemUpdateSchema = z.object({ status: z.enum(["saved", "favorite"]) });

const compactObject = (value) => Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined && item !== null));
export function toArchiveItemPayload(data) {
  return compactObject({
    title: data.title, public_job_id: data.public_job_id ?? data.publicJobId, image_url: data.image_url ?? data.imageUrl,
    thumbnail_url: data.thumbnail_url ?? data.thumbnailUrl, status: data.status ?? "saved", ad_format: data.ad_format ?? data.adFormat,
    platform: data.platform, source: data.source, workspace_id: data.workspace_id ?? data.workspaceId,
    user_id: data.user_id ?? data.userId, metadata: data.metadata
  });
}
