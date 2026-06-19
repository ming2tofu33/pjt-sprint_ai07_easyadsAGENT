import { z } from "zod";

export const adminReferenceSchema = z.object({
  templateId: z.string().trim().min(1).optional(), assetId: z.string().trim().min(1), workspaceId: z.string().trim().min(1).optional(),
  title: z.string().trim().min(1), description: z.string().optional().nullable(), category: z.string().trim().min(1),
  subCategory: z.string().optional().nullable(), tags: z.array(z.string()).optional(), businessTypes: z.array(z.string()).optional(),
  adFormats: z.array(z.string()).optional(), platforms: z.array(z.string()).optional(), aspectRatio: z.string().optional().nullable(),
  styleKeywords: z.array(z.string()).optional(), colorPalette: z.array(z.string()).optional(), layoutHint: z.string().optional().nullable(),
  typographyHint: z.string().optional().nullable(), backgroundStyle: z.string().optional().nullable(), popularityScore: z.number().min(0).optional(),
  status: z.enum(["active", "inactive", "draft"]).optional(), licenseNote: z.string().optional().nullable(),
  copyrightStatus: z.string().optional(), metadata: z.record(z.unknown()).optional()
});
export const adminReferenceUpdateSchema = adminReferenceSchema.omit({ assetId: true, workspaceId: true }).partial();
