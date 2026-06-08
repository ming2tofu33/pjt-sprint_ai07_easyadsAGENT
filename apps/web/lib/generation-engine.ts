export type ImageGenerationEngine = "gpt_image_1" | "gpt_image_2" | "flux_schnell" | "sd35_large";

export type GenerationRunMode = "graph_job";
export type DirectGenerationRunMode = "gpt_image_1_actual" | "gpt_image_2_actual" | "flux_schnell_real" | "sd35_large_real";
export type BackendImageEngine = "gpt_image_1" | "gpt_image_2" | "flux" | "sd35_large";

export type GenerationEngineOption = {
  id: ImageGenerationEngine;
  label: string;
  modelName: string;
  description: string;
  backendEngine: BackendImageEngine;
  directRunMode: DirectGenerationRunMode;
};

export const DEFAULT_IMAGE_GENERATION_ENGINE: ImageGenerationEngine = "gpt_image_1";

const stableGenerationEngineOptions: GenerationEngineOption[] = [
  {
    id: "gpt_image_1",
    label: "표준 OpenAI",
    modelName: "GPT-image-1",
    description: "예산을 지키면서 실제 광고 시안을 만들 때 적합해요.",
    backendEngine: "gpt_image_1",
    directRunMode: "gpt_image_1_actual"
  },
  {
    id: "flux_schnell",
    label: "빠른 생성",
    modelName: "FLUX.1-schnell",
    description: "빠르게 여러 방향을 확인할 때 좋아요.",
    backendEngine: "flux",
    directRunMode: "flux_schnell_real"
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

const experimentalGenerationEngineOptions: GenerationEngineOption[] = [
  {
    id: "gpt_image_2",
    label: "실험 고품질",
    modelName: "GPT-image-2",
    description: "제한된 예산으로 품질 비교가 필요할 때만 사용해요.",
    backendEngine: "gpt_image_2",
    directRunMode: "gpt_image_2_actual"
  }
];

export const allGenerationEngineOptions: GenerationEngineOption[] = [
  stableGenerationEngineOptions[0],
  ...experimentalGenerationEngineOptions,
  ...stableGenerationEngineOptions.slice(1)
];

export const generationEngineOptions: GenerationEngineOption[] = allGenerationEngineOptions;

export function getGenerationEngineOption(engine: ImageGenerationEngine | null | undefined): GenerationEngineOption {
  return allGenerationEngineOptions.find((option) => option.id === engine) ?? generationEngineOptions[0];
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
