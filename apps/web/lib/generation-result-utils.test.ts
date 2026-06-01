import { describe, expect, it } from "vitest";
import {
  buildGenerationResultCopyText,
  isDownloadEnabled,
  resolveDownloadUrl,
  resolvePreviewImageUrl
} from "./generation-result-utils";
import type { GenerationJob } from "./api-client";

const baseJob: GenerationJob = {
  job_id: "job_1",
  status: "done",
  progress: { progress_percent: 100, current_stage: "completed" },
  output_path: "data/outputs/job_1/final_0.png",
  result_payload: {
    schema_version: "result_artifact_v1",
    final_image_path: "data/outputs/job_1/final_0.png",
    download_url: null,
    final_image_url: null,
    engine: "mock",
    render_mode: "deterministic_mock",
    prompt_summary: { prompt_preview: "clean ad" },
    validation_summary: { overall_pass: true }
  }
};

describe("generation result utils", () => {
  it("disables download when no public URL exists", () => {
    expect(resolveDownloadUrl(baseJob)).toBeNull();
    expect(isDownloadEnabled(baseJob)).toBe(false);
  });

  it("uses public URL for preview and download when present", () => {
    const job = {
      ...baseJob,
      result_payload: { ...baseJob.result_payload, final_image_url: "/api/generated-assets?path=x", download_url: "/download/x" }
    };

    expect(resolvePreviewImageUrl(job)).toBe("/api/generated-assets?path=x");
    expect(resolveDownloadUrl(job)).toBe("/download/x");
    expect(isDownloadEnabled(job)).toBe(true);
  });

  it("does not use download_path as a public href", () => {
    const job = {
      ...baseJob,
      result_payload: { ...baseJob.result_payload, download_path: "data/outputs/job_1/final_0.png" }
    };

    expect(resolveDownloadUrl(job)).toBeNull();
  });

  it("builds copy text from job result payload", () => {
    const text = buildGenerationResultCopyText(baseJob);

    expect(text).toContain("Job ID: job_1");
    expect(text).toContain("Status: done");
    expect(text).toContain("Engine: mock");
    expect(text).toContain("Final image path: data/outputs/job_1/final_0.png");
  });

  it("maps repo output paths to the generated asset preview route", () => {
    expect(resolvePreviewImageUrl(baseJob)).toBe("/api/generated-assets?path=data%2Foutputs%2Fjob_1%2Ffinal_0.png");
  });
});
