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
      "reference-template-selection",
      "photo-final-source-image",
      "generation-selected-ui-state",
      "generation-copy-candidate-interrupt",
      "generation-custom-copy-interrupt",
      "reference.direct-image-upload",
      "validation-feedback"
    ]);
    expect(report.disconnectedIds).toEqual([]);
    expect(report.connectedCount).toBe(10);
    expect(report.totalCount).toBe(10);
  });

  it("marks the missing-context loop as a LangGraph interrupt/resume flow", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const row = findUiOrchestratorRouteCoverageRow(report, "context-question-loop");

    expect(row?.connected).toBe(true);
    expect(row?.executionMode).toBe("langgraph-interrupt-loop");
    expect(row?.apiCalls).toEqual(["POST /api/generate/chat/start", "POST /api/generate/chat/answer"]);
    expect(row?.graphNodesReached).toEqual(["input", "validator", "options", "state_update"]);
    expect(row?.fullGraphExecution).toBe(false);
    expect(row?.graphStateFields).toEqual(["thread_id", "context"]);
    expect(row?.testEvidence.length).toBeGreaterThan(0);
  });

  it("marks final generation as a full LangGraph generation job flow", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const row = findUiOrchestratorRouteCoverageRow(report, "final-model-generation");

    expect(row?.connected).toBe(true);
    expect(row?.executionMode).toBe("generation-job-graph");
    expect(row?.apiCalls).toEqual(["POST /api/generation-jobs", "GET /api/generation-jobs/{job_id}"]);
    expect(row?.fullGraphExecution).toBe(true);
    expect(row?.graphStateFields).toEqual(["image_generation_engine", "requested_engine", "t2i_engine"]);
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
    expect(row?.testEvidence).toEqual(
      expect.arrayContaining([
        "apps/web/app/generate/chat/ChatGenerateClient.test.tsx",
        "orchestrator/tests/test_generation_job_graph_execution.py"
      ])
    );
  });

  it("claims final generation as the current full graph route", () => {
    const report = buildUiOrchestratorRouteCoverageReport();

    expect(report.fullGraphIds).toEqual(["final-model-generation"]);
    expect(report.fullGraphCount).toBe(1);
    expect(report.directT2iIds).toEqual([]);
  });

  it("marks direct reference image upload connected only with UI, API, and graph state evidence", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const row = findUiOrchestratorRouteCoverageRow(report, "reference.direct-image-upload");

    expect(row).toMatchObject({
      connected: true,
      phase: "final-graph-integration-v1",
      graphStateFields: ["reference_image_path"],
      uiEntryPoints: ["ChatStartStep", "ChatGenerateClient"],
      apiCalls: ["POST /api/generate/photo/upload", "POST /api/generate/chat/start", "POST /api/generation-jobs"]
    });
  });

  it("keeps final graph integration gaps explicit until tests prove each state bridge", () => {
    const report = buildUiOrchestratorRouteCoverageReport();
    const finalGraphGaps = report.rows
      .filter((row) => row.phase === "final-graph-integration-v1" && !row.connected)
      .map((row) => [row.id, row.graphStateFields]);

    expect(finalGraphGaps).toEqual([]);
  });

  it("requires connected rows to carry implementation evidence", () => {
    const report = buildUiOrchestratorRouteCoverageReport();

    for (const row of report.rows.filter((item) => item.connected)) {
      expect(row.uiEntryPoints.length, `${row.id} needs UI entry evidence`).toBeGreaterThan(0);
      expect(row.apiCalls.length, `${row.id} needs API route evidence`).toBeGreaterThan(0);
      expect(row.graphNodesReached.length, `${row.id} needs graph node evidence`).toBeGreaterThan(0);
      expect(row.graphStateFields.length, `${row.id} needs graph state evidence`).toBeGreaterThan(0);
      expect(row.testEvidence.length, `${row.id} needs test file evidence`).toBeGreaterThan(0);
    }
  });

  it("keeps every row actionable with at least one entry point or bypassed graph node", () => {
    for (const row of UI_ORCHESTRATOR_ROUTE_COVERAGE) {
      expect(row.label.length, `${row.id} needs a readable label`).toBeGreaterThan(0);
      expect(row.notes.length, `${row.id} needs a diagnostic note`).toBeGreaterThan(0);
      expect(
        row.uiEntryPoints.length + row.graphNodesReached.length + row.graphNodesBypassed.length,
        `${row.id} needs implementation evidence`
      ).toBeGreaterThan(0);
      expect(row.phase.length, `${row.id} needs a coverage phase`).toBeGreaterThan(0);
      expect(Array.isArray(row.graphStateFields), `${row.id} needs graph state field metadata`).toBe(true);
      expect(Array.isArray(row.testEvidence), `${row.id} needs test evidence metadata`).toBe(true);
    }
  });
});
