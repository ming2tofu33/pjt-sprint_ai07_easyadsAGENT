import { describe, expect, it } from "vitest";
import {
  DEFAULT_IMAGE_GENERATION_ENGINE,
  getGenerationEngineOption,
  isTerminalGenerationJobStatus,
  resolveDirectGenerationRunMode,
  resolveGenerationEnginePreference,
  resolveGenerationRunMode
} from "./generation-engine";

describe("generation engine helpers", () => {
  it("uses the LangGraph run mode for final UI generation", () => {
    expect(resolveGenerationRunMode("gpt_image_2")).toBe("graph_job");
    expect(resolveGenerationRunMode("flux_schnell")).toBe("graph_job");
    expect(resolveGenerationRunMode("sd35_large")).toBe("graph_job");
  });

  it("maps UI engine choices to backend graph engine preferences", () => {
    expect(resolveGenerationEnginePreference("gpt_image_2")).toBe("gpt_image_2");
    expect(resolveGenerationEnginePreference("flux_schnell")).toBe("flux");
    expect(resolveGenerationEnginePreference("sd35_large")).toBe("sd35_large");
  });

  it("keeps direct T2I run modes available for smoke and debug paths", () => {
    expect(resolveDirectGenerationRunMode("gpt_image_2")).toBe("gpt_image_2_actual");
    expect(resolveDirectGenerationRunMode("flux_schnell")).toBe("flux_schnell_real");
    expect(resolveDirectGenerationRunMode("sd35_large")).toBe("sd35_large_real");
  });

  it("falls back to GPT-image-2 when no engine is selected", () => {
    expect(DEFAULT_IMAGE_GENERATION_ENGINE).toBe("gpt_image_2");
    expect(getGenerationEngineOption(null).id).toBe("gpt_image_2");
    expect(resolveGenerationRunMode(undefined)).toBe("graph_job");
    expect(resolveGenerationEnginePreference(undefined)).toBe("gpt_image_2");
  });

  it("identifies terminal generation job statuses", () => {
    expect(isTerminalGenerationJobStatus("done")).toBe(true);
    expect(isTerminalGenerationJobStatus("completed")).toBe(true);
    expect(isTerminalGenerationJobStatus("failed")).toBe(true);
    expect(isTerminalGenerationJobStatus("cancelled")).toBe(true);
    expect(isTerminalGenerationJobStatus("running")).toBe(false);
  });
});
