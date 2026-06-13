import { z } from "zod";

export const archiveItemCreateSchema = z
  .object({
    title: z.string().trim().min(1).max(200),
    public_job_id: z.string().trim().min(1).max(120).optional(),
    thumbnail_url: z.string().trim().min(1).optional().nullable(),
    image_url: z.string().trim().min(1).optional().nullable(),
    status: z.enum(["saved", "favorite", "failed"]).default("saved"),
    ad_format: z.string().trim().min(1).max(80).optional().nullable(),
    platform: z.string().trim().min(1).max(80).optional().nullable(),
    source: z.enum(["generated", "reference_template", "uploaded"]).default("generated"),
    workspace_id: z.string().trim().min(1).optional(),
    user_id: z.string().trim().min(1).optional(),
    account_type: z.enum(["guest", "user"]).optional(),
    metadata: z.record(z.unknown()).optional()
  })
  .superRefine((data, context) => {
    if (data.source === "generated" && !data.public_job_id) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["publicJobId"],
        message: "publicJobId is required for generated archive items"
      });
    }
    if (data.source !== "generated" && !data.image_url) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["imageUrl"],
        message: "imageUrl is required for uploaded or reference archive items"
      });
    }
  });

export const archiveItemUpdateSchema = z.object({
  status: z.enum(["saved", "favorite"])
});
