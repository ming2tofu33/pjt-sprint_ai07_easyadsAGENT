import { describe, expect, it } from "vitest";
import {
  buildUiOrchestratorRouteCoverageReport,
  findUiOrchestratorRouteCoverageRow,
  UI_ORCHESTRATOR_ROUTE_COVERAGE
} from "./ui-orchestrator-route-coverage";

describe("ui orchestrator route coverage", () => {
  it("documents which UI flows are currently connected to backend routes", () => {
    const report = buildUiOrchestratorRouteCoverageReport();

    expect(report.connectedIds).toEqual([
      "context-question-loop",
      "brief-confirmation",
      "final-model-generation",
      "reference-template-selection"
    ]);
    expect(report.disconnectedIds).toEqual(["reference-image-upload", "validation-feedback"]);
    expect(report.connectedCount).toBe(4);
    expect(report.totalCount).toBe(6);
  });

  it("marks the missing-context loop as a LangGraph interrupt/resume flow", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const row = findUiOrchestratorRouteCoverageRow(report, "context-question-loop");

    expect(row?.connected).toBe(true);
    expect(row?.executionMode).toBe("langgraph-interrupt-loop");
    expect(row?.apiCalls).toEqual(["POST /api/generate/chat/start", "POST /api/generate/chat/answer"]);
    expect(row?.graphNodesReached).toEqual(["input", "validator", "options", "state_update"]);
    expect(row?.fullGraphExecution).toBe(false);
  });

  it("marks final generation as a full LangGraph generation job flow", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const row = findUiOrchestratorRouteCoverageRow(report, "final-model-generation");

    expect(row?.connected).toBe(true);
    expect(row?.executionMode).toBe("generation-job-graph");
    expect(row?.apiCalls).toEqual(["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"]);
    expect(row?.fullGraphExecution).toBe(true);
    expect(row?.graphNodesReached).toEqual(
      expect.arrayContaining([
        "format_planner",
        "tone_binding",
        "copy_spec_parser",
        "image_prompt_planner",
        "prompt_renderer",
        "t2i_request_builder",
        "t2i_generation",
        "background_validation",
        "safe_area_gate",
        "readability_gate",
        "final_validation",
        "result"
      ])
    );
    expect(row?.graphNodesBypassed).toEqual([]);
  });

  it("claims final generation as the current full graph route", () => {
    const report = buildUiOrchestratorRouteCoverageReport();

    expect(report.fullGraphIds).toEqual(["final-model-generation"]);
    expect(report.fullGraphCount).toBe(1);
    expect(report.directT2iIds).toEqual([]);
  });

  it("keeps every row actionable with at least one entry point or bypassed graph node", () => {
    for (const row of UI_ORCHESTRATOR_ROUTE_COVERAGE) {
      expect(row.label.length, `${row.id} needs a readable label`).toBeGreaterThan(0);
      expect(row.notes.length, `${row.id} needs a diagnostic note`).toBeGreaterThan(0);
      expect(
        row.uiEntryPoints.length + row.graphNodesReached.length + row.graphNodesBypassed.length,
        `${row.id} needs implementation evidence`
      ).toBeGreaterThan(0);
    }
  });
});
