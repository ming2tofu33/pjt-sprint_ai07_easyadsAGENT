import { z } from "zod";
import { SUPPORTED_IMAGE_GENERATION_ENGINES } from "@/lib/generation-engine";

export const copyGenerationModes = ["suggest_candidates", "auto_pilot", "custom_input", "no_copy"] as const;
export const supportedPhotoMimeTypes = ["image/png", "image/jpeg", "image/webp"] as const;
export const supportedImageGenerationEngines = SUPPORTED_IMAGE_GENERATION_ENGINES;

const customCopyFieldsSchema = {
  userCustomHeadline: z.string().trim().min(1).optional(),
  userCustomSubcopy: z.string().trim().optional()
};

const referenceTemplateFieldsSchema = {
  selectedReferenceTemplateId: z.string().trim().min(1).optional()
};

const referenceImageFieldsSchema = {
  referenceAssetId: z.string().trim().min(1).optional(),
  referenceImagePath: z.never().optional()
};

const imageGenerationEngineFieldsSchema = {
  imageGenerationEngine: z.enum(supportedImageGenerationEngines).optional(),
  requestedEngine: z.enum(supportedImageGenerationEngines).optional(),
  t2iEngine: z.enum(supportedImageGenerationEngines).optional(),
  selectedEngineLabel: z.string().trim().min(1).optional()
};

function requireHeadlineForCustomInput(
  data: { copyGenerationMode?: string; userCustomHeadline?: string },
  context: z.RefinementCtx
) {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["userCustomHeadline"],
      message: "userCustomHeadline is required for custom_input"
    });
  }
}

export const chatStartSchema = z
  .object({
    userInput: z.string().trim().min(1),
    adFormat: z.string().optional(),
    renderProfile: z.string().optional(),
    copyGenerationMode: z.enum(copyGenerationModes).optional(),
    ...customCopyFieldsSchema,
    ...referenceTemplateFieldsSchema,
    ...referenceImageFieldsSchema,
    ...imageGenerationEngineFieldsSchema
  })
  .superRefine(requireHeadlineForCustomInput);

export const chatBriefSchema = z.object({
  jobId: z.string().trim().min(1),
  threadId: z.string().trim().min(1),
  selectedCopyId: z.string().trim().min(1),
  selectedChannelId: z.string().optional(),
  selectedTone: z.string().optional(),
  customDirection: z.string().optional()
});

export const chatAnswerSchema = z.object({
  jobId: z.string().trim().min(1),
  threadId: z.string().trim().min(1),
  field: z.string().trim().min(1),
  value: z.string(),
  customText: z.string().optional()
});

export const photoUploadSchema = z.object({
  filename: z.string().trim().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  dataUrl: z.string().trim().min(1)
});

export const photoStartSchema = z
  .object({
    userInput: z.string().trim().min(1),
    sourceAssetId: z.string().trim().min(1),
    sourceImagePath: z.never().optional(),
    adFormat: z.string().optional(),
    renderProfile: z.string().optional(),
    copyGenerationMode: z.enum(copyGenerationModes).optional(),
    ...customCopyFieldsSchema,
    ...referenceTemplateFieldsSchema,
    ...referenceImageFieldsSchema,
    ...imageGenerationEngineFieldsSchema
  })
  .superRefine(requireHeadlineForCustomInput);

export const generationJobSchema = z
  .object({
    user_input: z.string().optional(),
    userInput: z.string().optional(),
    thread_id: z.string().trim().min(1).optional(),
    threadId: z.string().trim().min(1).optional(),
    user_id: z.string().optional(),
    userId: z.string().optional(),
    run_mode: z.string().optional(),
    runMode: z.string().optional(),
    image_generation_engine: z.enum(supportedImageGenerationEngines).optional(),
    imageGenerationEngine: z.enum(supportedImageGenerationEngines).optional(),
    requested_engine: z.enum(supportedImageGenerationEngines).optional(),
    requestedEngine: z.enum(supportedImageGenerationEngines).optional(),
    t2i_engine: z.enum(supportedImageGenerationEngines).optional(),
    t2iEngine: z.enum(supportedImageGenerationEngines).optional(),
    selected_reference_template_id: z.string().optional(),
    selectedReferenceTemplateId: z.string().optional(),
    selected_copy_id: z.string().optional(),
    selectedCopyId: z.string().optional(),
    selected_channel_id: z.string().optional(),
    selectedChannelId: z.string().optional(),
    selected_tone: z.string().optional(),
    selectedTone: z.string().optional(),
    custom_direction: z.string().optional(),
    customDirection: z.string().optional(),
    user_custom_headline: z.string().optional(),
    userCustomHeadline: z.string().optional(),
    user_custom_subcopy: z.string().optional(),
    userCustomSubcopy: z.string().optional(),
    source_asset_id: z.string().optional(),
    sourceAssetId: z.string().optional(),
    reference_asset_id: z.string().optional(),
    referenceAssetId: z.string().optional(),
    source_image_path: z.never().optional(),
    sourceImagePath: z.never().optional(),
    reference_image_path: z.never().optional(),
    referenceImagePath: z.never().optional()
  })
  .passthrough();

export const generationJobAnswerSchema = z
  .object({
    field: z.string().trim().min(1).optional(),
    value: z.string().optional(),
    customText: z.string().optional(),
    selectedCopyId: z.string().optional(),
    userCustomHeadline: z.string().optional(),
    userCustomSubcopy: z.string().optional(),
    payload: z.record(z.unknown()).optional()
  })
  .passthrough();

export const archiveItemSchema = z.object({
  title: z.string().trim().min(1),
  publicJobId: z.string().trim().min(1).optional(),
  public_job_id: z.string().trim().min(1).optional(),
  imageUrl: z.string().trim().min(1).optional().nullable(),
  image_url: z.string().trim().min(1).optional().nullable(),
  thumbnailUrl: z.string().trim().min(1).optional().nullable(),
  thumbnail_url: z.string().trim().min(1).optional().nullable(),
  status: z.enum(["saved", "favorite", "failed"]).optional(),
  adFormat: z.string().trim().min(1).optional().nullable(),
  ad_format: z.string().trim().min(1).optional().nullable(),
  platform: z.string().trim().min(1).optional().nullable(),
  source: z.enum(["generated", "reference_template", "uploaded"]).optional(),
  workspaceId: z.string().trim().min(1).optional(),
  workspace_id: z.string().trim().min(1).optional(),
  userId: z.string().trim().min(1).optional(),
  user_id: z.string().trim().min(1).optional(),
  metadata: z.record(z.unknown()).optional()
});

export const archiveItemUpdateSchema = z.object({
  status: z.enum(["saved", "favorite"])
});

export const assetPresignSchema = z.object({
  kind: z.enum(["upload", "source", "reference"]),
  filename: z.string().trim().min(1),
  mimeType: z.enum(supportedPhotoMimeTypes),
  sizeBytes: z.number().int().positive(),
  workspaceId: z.string().trim().min(1).optional(),
  threadId: z.string().trim().min(1).optional()
});

export const assetCompleteSchema = z.object({
  workspaceId: z.string().trim().min(1).optional(),
  threadId: z.string().trim().min(1).optional(),
  status: z.enum(["uploaded", "failed"]).optional(),
  metadata: z.record(z.unknown()).optional()
});

export const adminReferenceSchema = z.object({
  templateId: z.string().trim().min(1).optional(),
  assetId: z.string().trim().min(1),
  workspaceId: z.string().trim().min(1).optional(),
  title: z.string().trim().min(1),
  description: z.string().optional().nullable(),
  category: z.string().trim().min(1),
  subCategory: z.string().optional().nullable(),
  tags: z.array(z.string()).optional(),
  businessTypes: z.array(z.string()).optional(),
  adFormats: z.array(z.string()).optional(),
  platforms: z.array(z.string()).optional(),
  aspectRatio: z.string().optional().nullable(),
  styleKeywords: z.array(z.string()).optional(),
  colorPalette: z.array(z.string()).optional(),
  layoutHint: z.string().optional().nullable(),
  typographyHint: z.string().optional().nullable(),
  backgroundStyle: z.string().optional().nullable(),
  popularityScore: z.number().min(0).optional(),
  status: z.enum(["active", "inactive", "draft"]).optional(),
  licenseNote: z.string().optional().nullable(),
  copyrightStatus: z.string().optional(),
  metadata: z.record(z.unknown()).optional()
});

export const adminReferenceUpdateSchema = adminReferenceSchema.omit({ assetId: true, workspaceId: true }).partial();
