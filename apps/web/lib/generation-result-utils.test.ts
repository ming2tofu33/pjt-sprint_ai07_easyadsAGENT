import { describe, expect, it } from "vitest";
import {
  buildGenerationResultCopyText,
  getDisplayImageUrl,
  getDownloadUrl,
  getGenerationResultNotice,
  getResultArtifactPayload,
  hasOnlyLocalArtifactPath,
  isDownloadEnabled,
  isSuccessfulGenerationJob,
  isTerminalGenerationStatus,
  resolveDownloadUrl,
  resolvePreviewImageUrl,
  shouldEnableDownload,
  shouldShowImagePreview
} from "./generation-result-utils";
import type { GenerationJob } from "./api-client";

const doneJobWithUrl: GenerationJob = {
  job_id: "job_url",
  status: "done",
  progress_percent: 100,
  current_stage: "completed",
  result_payload: {
    schema_version: "result_artifact_v1",
    final_image_url: "https://cdn.example.com/generated/job_url/final_0.png",
    download_url: "https://cdn.example.com/generated/job_url/final_0.png",
    final_image_path: "data/outputs/job_url/final_0.png",
    download_path: "data/outputs/job_url/final_0.png",
    prompt_summary: { engine: "gpt_image_2", image_prompt_version: "v3" },
    validation_summary: { overall_pass: true },
    copy_summary: { headline: "딸기라떼 신메뉴" },
    layout_summary: { reserved_text_areas_count: 1 },
    engine: "gpt_image_2",
    render_mode: "actual"
  },
  metadata: { requested_run_mode: "gpt_image_2_actual", effective_run_mode: "gpt_image_2_actual" }
};

const doneJobLocalPathOnly: GenerationJob = {
  job_id: "job_local",
  status: "done",
  progress_percent: 100,
  current_stage: "completed",
  output_path: "data/outputs/job_local/final_0.png",
  result_payload: {
    schema_version: "result_artifact_v1",
    final_image_url: null,
    download_url: null,
    final_image_path: "data/outputs/job_local/final_0.png",
    download_path: "data/outputs/job_local/final_0.png",
    prompt_summary: { engine: "gpt_image_2", image_prompt_version: "v3" }
  }
};

const failedJob: GenerationJob = {
  job_id: "job_failed",
  status: "failed",
  error: {
    error_code: "t2i_engine_unavailable",
    message: "T2I generation failed."
  }
};

const runningJob: GenerationJob = {
  job_id: "job_running",
  status: "running",
  progress_percent: 50,
  current_stage: "generating_image"
};

describe("generation result utils", () => {
  it("detects terminal and successful generation statuses", () => {
    expect(isTerminalGenerationStatus("done")).toBe(true);
    expect(isTerminalGenerationStatus("failed")).toBe(true);
    expect(isTerminalGenerationStatus("running")).toBe(false);
    expect(isSuccessfulGenerationJob(doneJobWithUrl)).toBe(true);
    expect(isSuccessfulGenerationJob(failedJob)).toBe(false);
  });

  it("returns result artifact payload from a job", () => {
    expect(getResultArtifactPayload(doneJobWithUrl)?.schema_version).toBe("result_artifact_v1");
    expect(getResultArtifactPayload(null)).toBeNull();
  });

  it("uses public URLs for preview and download when present", () => {
    const payload = doneJobWithUrl.result_payload;

    expect(getDisplayImageUrl(payload)).toBe("https://cdn.example.com/generated/job_url/final_0.png");
    expect(getDownloadUrl(payload)).toBe("https://cdn.example.com/generated/job_url/final_0.png");
    expect(resolvePreviewImageUrl(doneJobWithUrl)).toBe("https://cdn.example.com/generated/job_url/final_0.png");
    expect(resolveDownloadUrl(doneJobWithUrl)).toBe("https://cdn.example.com/generated/job_url/final_0.png");
    expect(shouldShowImagePreview(payload)).toBe(true);
    expect(shouldEnableDownload(payload)).toBe(true);
    expect(isDownloadEnabled(doneJobWithUrl)).toBe(true);
  });

  it("does not use local artifact paths as preview or download URLs", () => {
    const payload = doneJobLocalPathOnly.result_payload;

    expect(getDisplayImageUrl(payload)).toBeNull();
    expect(getDownloadUrl(payload)).toBeNull();
    expect(resolvePreviewImageUrl(doneJobLocalPathOnly)).toBeNull();
    expect(resolveDownloadUrl(doneJobLocalPathOnly)).toBeNull();
    expect(shouldShowImagePreview(payload)).toBe(false);
    expect(shouldEnableDownload(payload)).toBe(false);
    expect(hasOnlyLocalArtifactPath(payload)).toBe(true);
    expect(isDownloadEnabled(doneJobLocalPathOnly)).toBe(false);
  });

  it("prefers preview and copy visual URLs before download URL for display", () => {
    expect(getDisplayImageUrl({ preview_image_url: "/api/generated/preview.png", download_url: "/api/generated/download.png" })).toBe(
      "/api/generated/preview.png"
    );
    expect(getDisplayImageUrl({ copy_visual_preview_url: "/api/generated/copy-preview.png", download_url: "/api/generated/download.png" })).toBe(
      "/api/generated/copy-preview.png"
    );
  });

  it("builds copy text without exposing local data output paths", () => {
    const withSecretLikeSummary: GenerationJob = {
      ...doneJobLocalPathOnly,
      result_payload: {
        ...doneJobLocalPathOnly.result_payload,
        validation_summary: {
          final_image_path: "data/outputs/job_local/final_0.png",
          warnings: ["safe_area_complex_background"],
          raw_prompt: "very long raw prompt should not be copied"
        }
      }
    };

    const text = buildGenerationResultCopyText(withSecretLikeSummary);

    expect(text).toContain("Job ID: job_local");
    expect(text).toContain("Status: done");
    expect(text).toContain("Image URL: not available yet");
    expect(text).toContain("Download URL: not available yet");
    expect(text).not.toContain("data/outputs/job_local/final_0.png");
    expect(text).not.toContain("very long raw prompt");
    expect(text).toContain("Warnings: safe_area_complex_background");
  });

  it("keeps public URLs in copy text when available", () => {
    const text = buildGenerationResultCopyText(doneJobWithUrl);

    expect(text).toContain("https://cdn.example.com/generated/job_url/final_0.png");
    expect(text).not.toContain("data/outputs/job_url/final_0.png");
  });

  it("sanitizes nested secret-like summary fields", () => {
    const job: GenerationJob = {
      ...doneJobWithUrl,
      result_payload: {
        ...doneJobWithUrl.result_payload,
        validation_summary: {
          warnings: ["ok"],
          nested: {
            api_key: "sk-should-not-leak",
            raw_prompt: "raw prompt should not leak",
            final_image_path: "data/outputs/job/final_0.png",
            safe: "visible"
          }
        }
      }
    };

    const text = buildGenerationResultCopyText(job);

    expect(text).not.toContain("sk-should-not-leak");
    expect(text).not.toContain("raw prompt should not leak");
    expect(text).not.toContain("data/outputs/job/final_0.png");
    expect(text).toContain("visible");
  });

  it("returns status-specific notices", () => {
    expect(getGenerationResultNotice(doneJobWithUrl)).toEqual({
      level: "success",
      message: "완성된 이미지를 확인할 수 있어요."
    });
    expect(getGenerationResultNotice(doneJobLocalPathOnly)).toEqual({
      level: "warning",
      message: "이미지는 생성됐지만 아직 화면에서 바로 열 수 없어요."
    });
    expect(getGenerationResultNotice(failedJob).level).toBe("error");
    expect(getGenerationResultNotice(runningJob)).toEqual({ level: "info", message: "이미지를 생성하고 있어요." });
  });

  it("keeps failed and running jobs without preview or download", () => {
    expect(shouldShowImagePreview(failedJob.result_payload)).toBe(false);
    expect(isDownloadEnabled(failedJob)).toBe(false);
    expect(isTerminalGenerationStatus(runningJob.status)).toBe(false);
    expect(isDownloadEnabled(runningJob)).toBe(false);
  });
});
