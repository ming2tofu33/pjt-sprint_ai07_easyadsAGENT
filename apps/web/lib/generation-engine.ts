export const SUPPORTED_IMAGE_GENERATION_ENGINES = ["gpt_image_2", "flux2_klein_4b", "sd35_large"] as const;

export type ImageGenerationEngine = (typeof SUPPORTED_IMAGE_GENERATION_ENGINES)[number];

export type GenerationRunMode = "graph_job";
export type DirectGenerationRunMode = "gpt_image_2_actual" | "flux2_klein_4b" | "sd35_large_real";
export type BackendImageEngine = ImageGenerationEngine;

export type GenerationEngineOption = {
  id: ImageGenerationEngine;
  label: string;
  modelName: string;
  description: string;
  backendEngine: BackendImageEngine;
  directRunMode: DirectGenerationRunMode;
};

export const DEFAULT_IMAGE_GENERATION_ENGINE: ImageGenerationEngine = "gpt_image_2";

export const generationEngineOptions: GenerationEngineOption[] = [
  {
    id: "gpt_image_2",
    label: "기본 OpenAI",
    modelName: "GPT-image-2",
    description: "기본으로 사용하는 OpenAI 이미지 모델이에요.",
    backendEngine: "gpt_image_2",
    directRunMode: "gpt_image_2_actual"
  },
  {
    id: "flux2_klein_4b",
    label: "오픈 모델",
    modelName: "FLUX.2 Klein 4B",
    description: "Modal에서 실행하는 FLUX.2 모델로 광고 시안을 만들어요.",
    backendEngine: "flux2_klein_4b",
    directRunMode: "flux2_klein_4b"
  },
  {
    id: "sd35_large",
    label: "정교한 이미지",
    modelName: "SD3.5 Large",
    description: "디테일한 이미지 구성이 필요할 때 사용해요.",
    backendEngine: "sd35_large",
    directRunMode: "sd35_large_real"
  }
];

export const allGenerationEngineOptions: GenerationEngineOption[] = generationEngineOptions;

export function normalizeImageGenerationEngine(value: unknown): ImageGenerationEngine {
  if (value === "gpt_image_1") {
    return DEFAULT_IMAGE_GENERATION_ENGINE;
  }
  if (value === "flux" || value === "flux_schnell" || value === "flux_1_schnell" || value === "flux2_klein") {
    return "flux2_klein_4b";
  }
  if (SUPPORTED_IMAGE_GENERATION_ENGINES.includes(value as ImageGenerationEngine)) {
    return value as ImageGenerationEngine;
  }
  return DEFAULT_IMAGE_GENERATION_ENGINE;
}

export function getGenerationEngineOption(engine: unknown): GenerationEngineOption {
  const normalized = normalizeImageGenerationEngine(engine);
  return allGenerationEngineOptions.find((option) => option.id === normalized) ?? generationEngineOptions[0];
}

export function resolveGenerationRunMode(_engine: ImageGenerationEngine | null | undefined): GenerationRunMode {
  return "graph_job";
}

export function resolveGenerationEnginePreference(engine: ImageGenerationEngine | null | undefined): BackendImageEngine {
  return getGenerationEngineOption(engine).backendEngine;
}

export function resolveDirectGenerationRunMode(engine: ImageGenerationEngine | null | undefined): DirectGenerationRunMode {
  return getGenerationEngineOption(engine).directRunMode;
}

export function isTerminalGenerationJobStatus(status: string | null | undefined): boolean {
  return status === "done" || status === "completed" || status === "failed" || status === "cancelled";
}
