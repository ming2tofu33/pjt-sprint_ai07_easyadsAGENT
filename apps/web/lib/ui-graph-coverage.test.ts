import { describe, expect, it } from "vitest";
import {
  buildUiGraphCoverageReport,
  CURRENT_UI_GRAPH_CAPABILITIES,
  findUiGraphCoverageItem,
  UI_GRAPH_COVERAGE_MATRIX,
  type UiGraphCapability,
} from "./ui-graph-coverage";

const KNOWN_GRAPH_NODES = new Set([
  "input",
  "reference_template_resolve",
  "product_preprocess",
  "reference_preprocess",
  "validator",
  "options",
  "state_update",
  "format_planner",
  "tone_binding",
  "copy_candidate_generation",
  "copy_candidate_selection_interrupt",
  "state_update_selected_copy",
  "auto_pilot_copywriting",
  "custom_copy_input",
  "custom_copy_validation",
  "no_copy_bypass",
  "copy_spec_parser",
  "text_style_binder",
  "text_layout_planner",
  "image_prompt_planner",
  "prompt_renderer",
  "t2i_request_builder",
  "t2i_generation",
  "background_validation",
  "safe_area_gate",
  "text_renderer",
  "readability_gate",
  "final_validation",
  "result",
]);

const ALL_CAPABILITIES: UiGraphCapability[] = [
  "chat.start",
  "chat.answer-context-question",
  "generation-job.answer-context-question",
  "copy-mode.suggest-candidates",
  "copy-selection.copy-channel-tone",
  "copy-selection.visual-direction",
  "photo.upload-source-image",
  "photo.start",
  "copy-mode.auto-pilot",
  "copy-mode.custom-input",
  "copy.custom-headline-input",
  "copy-mode.no-copy",
  "reference.template-selection",
  "reference.image-upload",
  "validation.reports-visible",
];

describe("ui graph coverage matrix", () => {
  it("reports the graph branches currently reachable from the UI", () => {
    const report = buildUiGraphCoverageReport();

    expect(report.coveredIds).toEqual([
      "missing-context-loop",
      "generation-job-context-loop",
      "chat-suggest-candidates",
      "photo-source-suggest-candidates",
      "custom-visual-direction",
      "auto-pilot-copywriting",
      "custom-copy-input",
      "no-copy-image-only",
      "reference-template",
    ]);
    expect(report.uncoveredIds).toEqual([
      "reference-image",
      "validation-feedback",
    ]);
    expect(report.coveredCount).toBe(9);
    expect(report.totalCount).toBe(11);
    expect(report.coverageRatio).toBe(9 / 11);
  });

  it("shows the exact UI capabilities missing for each uncovered branch", () => {
    const report = buildUiGraphCoverageReport();

    expect(findUiGraphCoverageItem(report, "generation-job-context-loop")?.missingCapabilities).toEqual([]);
    expect(findUiGraphCoverageItem(report, "auto-pilot-copywriting")?.missingCapabilities).toEqual([]);
    expect(findUiGraphCoverageItem(report, "custom-copy-input")?.missingCapabilities).toEqual([]);
    expect(findUiGraphCoverageItem(report, "no-copy-image-only")?.missingCapabilities).toEqual([]);
    expect(findUiGraphCoverageItem(report, "reference-template")?.missingCapabilities).toEqual([]);
    expect(findUiGraphCoverageItem(report, "reference-image")?.missingCapabilities).toEqual(["reference.image-upload"]);
    expect(findUiGraphCoverageItem(report, "validation-feedback")?.missingCapabilities).toEqual(["validation.reports-visible"]);
  });

  it("marks all matrix rows covered once the missing UI capabilities exist", () => {
    const report = buildUiGraphCoverageReport(ALL_CAPABILITIES);

    expect(report.uncoveredIds).toEqual([]);
    expect(report.coveredCount).toBe(UI_GRAPH_COVERAGE_MATRIX.length);
    expect(report.coverageRatio).toBe(1);
  });

  it("keeps matrix rows tied to known graph node names and declared capabilities", () => {
    const declaredCapabilities = new Set(ALL_CAPABILITIES);

    expect(new Set(CURRENT_UI_GRAPH_CAPABILITIES).size).toBe(CURRENT_UI_GRAPH_CAPABILITIES.length);
    for (const item of UI_GRAPH_COVERAGE_MATRIX) {
      expect(item.requiredCapabilities.length, `${item.id} must declare required UI capabilities`).toBeGreaterThan(0);
      expect(item.expectedGraphNodes.length, `${item.id} must declare expected graph nodes`).toBeGreaterThan(0);
      for (const capability of item.requiredCapabilities) {
        expect(declaredCapabilities.has(capability), `${item.id} uses unknown capability ${capability}`).toBe(true);
      }
      for (const nodeName of item.expectedGraphNodes) {
        expect(KNOWN_GRAPH_NODES.has(nodeName), `${item.id} uses unknown graph node ${nodeName}`).toBe(true);
      }
    }
  });
});
