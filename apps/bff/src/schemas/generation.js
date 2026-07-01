import { z } from "zod";
import { imageGenerationEngines } from "../contracts/generation-engines.js";

export const copyGenerationModes = ["suggest_candidates", "auto_pilot", "custom_input", "no_copy"];
const customCopyFields = { userCustomHeadline: z.string().trim().min(1).optional(), userCustomSubcopy: z.string().trim().optional() };
const referenceTemplateFields = { selectedReferenceTemplateId: z.string().trim().min(1).optional() };
const referenceImageFields = { referenceAssetId: z.string().trim().min(1).optional(), referenceImagePath: z.never().optional() };
const engineFields = {
  imageGenerationEngine: z.enum(imageGenerationEngines).optional(),
  requestedEngine: z.enum(imageGenerationEngines).optional(),
  t2iEngine: z.enum(imageGenerationEngines).optional(),
  selectedEngineLabel: z.string().trim().min(1).optional()
};

function requireCustomHeadline(data, context) {
  if (data.copyGenerationMode === "custom_input" && !data.userCustomHeadline) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["userCustomHeadline"], message: "userCustomHeadline is required for custom_input" });
  }
}

export const chatStartSchema = z.object({
  userInput: z.string().min(1), adFormat: z.string().optional(), renderProfile: z.string().optional(),
  copyGenerationMode: z.enum(copyGenerationModes).optional(), ...customCopyFields, ...referenceTemplateFields,
  ...referenceImageFields, ...engineFields
}).superRefine(requireCustomHeadline);

export const chatBriefSchema = z.object({
  jobId: z.string().min(1), threadId: z.string().min(1), selectedCopyId: z.string().min(1),
  selectedChannelId: z.string().optional(), selectedTone: z.string().optional(), customDirection: z.string().optional()
});

export const chatAnswerSchema = z.object({
  jobId: z.string().min(1), threadId: z.string().min(1), field: z.string().min(1), value: z.string(), customText: z.string().optional()
});

export const photoUploadSchema = z.object({
  filename: z.string().min(1), mimeType: z.enum(["image/png", "image/jpeg", "image/webp"]), dataUrl: z.string().min(1)
});

export const photoStartSchema = z.object({
  userInput: z.string().min(1), sourceAssetId: z.string().min(1), sourceImagePath: z.never().optional(),
  adFormat: z.string().optional(), renderProfile: z.string().optional(), copyGenerationMode: z.enum(copyGenerationModes).optional(),
  ...customCopyFields, ...referenceTemplateFields, ...referenceImageFields, ...engineFields
}).superRefine(requireCustomHeadline);

export const generationJobSchema = z.object({
  user_input: z.string().optional(), userInput: z.string().optional(), thread_id: z.string().trim().min(1).optional(), threadId: z.string().trim().min(1).optional(),
  user_id: z.string().optional(), userId: z.string().optional(), run_mode: z.string().optional(), runMode: z.string().optional(),
  image_generation_engine: z.enum(imageGenerationEngines).optional(), imageGenerationEngine: z.enum(imageGenerationEngines).optional(),
  requested_engine: z.enum(imageGenerationEngines).optional(), requestedEngine: z.enum(imageGenerationEngines).optional(),
  t2i_engine: z.enum(imageGenerationEngines).optional(), t2iEngine: z.enum(imageGenerationEngines).optional(),
  selected_reference_template_id: z.string().optional(), selectedReferenceTemplateId: z.string().optional(),
  selected_copy_id: z.string().optional(), selectedCopyId: z.string().optional(), selected_channel_id: z.string().optional(), selectedChannelId: z.string().optional(),
  source_asset_id: z.string().optional(), sourceAssetId: z.string().optional(), reference_asset_id: z.string().optional(), referenceAssetId: z.string().optional(),
  selected_tone: z.string().optional(), selectedTone: z.string().optional(), custom_direction: z.string().optional(), customDirection: z.string().optional(),
  user_custom_headline: z.string().optional(), userCustomHeadline: z.string().optional(), user_custom_subcopy: z.string().optional(), userCustomSubcopy: z.string().optional(),
  source_image_path: z.never().optional(), sourceImagePath: z.never().optional(), reference_image_path: z.never().optional(), referenceImagePath: z.never().optional()
}).passthrough();

export const generationJobAnswerSchema = z.object({
  field: z.string().trim().min(1).optional(), value: z.string().optional(), customText: z.string().optional(), selectedCopyId: z.string().optional(),
  userCustomHeadline: z.string().optional(), userCustomSubcopy: z.string().optional(), payload: z.record(z.unknown()).optional()
}).passthrough();
