export type ImageGenerationEngine = "gpt_image_2" | "flux_schnell" | "sd35_large";

export type GenerationRunMode = "graph_immediate";
export type DirectGenerationRunMode = "gpt_image_2_actual" | "flux_schnell_real" | "sd35_large_real";
export type BackendImageEngine = "gpt_image_2" | "flux" | "sd35_large";

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
    label: "고품질 이미지",
    modelName: "GPT-image-2",
    description: "완성도 높은 광고 시안에 적합해요.",
    backendEngine: "gpt_image_2",
    directRunMode: "gpt_image_2_actual"
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

export function getGenerationEngineOption(engine: ImageGenerationEngine | null | undefined): GenerationEngineOption {
  return generationEngineOptions.find((option) => option.id === engine) ?? generationEngineOptions[0];
}

export function resolveGenerationRunMode(_engine: ImageGenerationEngine | null | undefined): GenerationRunMode {
  return "graph_immediate";
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
