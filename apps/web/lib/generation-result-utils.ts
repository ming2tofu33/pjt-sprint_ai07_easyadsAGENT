import type { GenerationJob, ResultArtifactPayload } from "./api-client";

const LOCAL_PATH_PREFIXES = [
  "data/outputs/",
  "data/logs/",
  "./data/",
  "../data/",
  "/home/",
  "/tmp/",
  "/mnt/",
  "file://"
];

export type ValidationFeedbackStatus = "pass" | "warn" | "fail";

export type ValidationFeedbackItem = {
  id: "background" | "safe_area" | "readability" | "final" | "ocr" | "compliance";
  label: string;
  status: ValidationFeedbackStatus;
  message: string;
};

export function isTerminalGenerationStatus(status: string | undefined | null): boolean {
  return status === "done" || status === "failed";
}

export function isSuccessfulGenerationJob(job: GenerationJob | null | undefined): boolean {
  return job?.status === "done";
}

export function getResultArtifactPayload(job: GenerationJob | null | undefined): ResultArtifactPayload | null {
  return job?.result_payload ?? null;
}

export function buildValidationFeedbackItems(summary: Record<string, unknown> | null | undefined): ValidationFeedbackItem[] {
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) {
    return [];
  }

  const nestedItems: ValidationFeedbackItem[] = [
    validationItem("background", "배경 확인", summary.background, {
      pass: "이미지 배경이 광고로 쓰기 좋게 준비됐어요.",
      warn: "배경에서 한 번 더 확인하면 좋은 부분이 있어요.",
      fail: "배경 이미지 확인이 필요해요."
    }),
    validationItem("safe_area", "문구 위치 확인", summary.safe_area, {
      pass: "문구가 들어갈 공간이 안정적이에요.",
      warn: "문구가 들어갈 위치를 한 번 더 확인해보세요.",
      fail: "문구 위치를 조정하는 편이 좋아요."
    }),
    validationItem("readability", "가독성 확인", summary.readability, {
      pass: "문구를 읽기 쉬운 상태예요.",
      warn: "문구가 더 잘 보이도록 조정하면 좋아요.",
      fail: "문구 가독성 개선이 필요해요."
    }),
    validationItem("final", "최종 확인", summary.final, {
      pass: "전체 결과가 사용 가능한 상태예요.",
      warn: "사용 전 한 번 더 살펴보면 좋아요.",
      fail: "최종 결과를 다시 조정하는 편이 좋아요."
    })
  ].filter((item): item is ValidationFeedbackItem => Boolean(item));

  if (nestedItems.length > 0) {
    return nestedItems;
  }

  const fallback = validationItem("final", "최종 확인", summary, {
    pass: "전체 결과가 사용 가능한 상태예요.",
    warn: "사용 전 한 번 더 살펴보면 좋아요.",
    fail: "최종 결과를 다시 조정하는 편이 좋아요."
  });
  return fallback ? [fallback] : [];
}

export function buildResultReviewItems(payload: ResultArtifactPayload | null | undefined): ValidationFeedbackItem[] {
  if (!payload) {
    return [];
  }

  const items = buildValidationFeedbackItems(payload.validation_summary ?? null);
  const ocrDecision = safeString(payload.qualityDecision) || safeString(payload.ocr_gate?.decision);

  if (payload.qualityRejected || ocrDecision === "reject") {
    items.push({
      id: "ocr",
      label: "문구 검수",
      status: "fail",
      message: "이미지 안의 문구가 기준을 통과하지 못했어요."
    });
  } else if (payload.requiresManualReview || ["manual_review", "unavailable", "retry_image", "retry_layout"].includes(ocrDecision ?? "")) {
    items.push({
      id: "ocr",
      label: "문구 검수",
      status: "warn",
      message: "사용 전에 이미지 안의 문구를 한 번 더 확인해주세요."
    });
  } else if (ocrDecision === "pass") {
    items.push({
      id: "ocr",
      label: "문구 검수",
      status: "pass",
      message: "이미지 안의 문구가 요청한 내용과 잘 맞아요."
    });
  }

  const compliance = payload.compliance;
  if (compliance?.status === "blocked") {
    items.push({
      id: "compliance",
      label: "광고 표현 확인",
      status: "fail",
      message: compliance.summary || "광고 표현 기준을 통과하지 못했어요."
    });
  } else if (compliance?.status === "rewritten" || compliance?.status === "needs_review") {
    items.push({
      id: "compliance",
      label: "광고 표현 확인",
      status: "warn",
      message: compliance.summary || "일부 표현은 사용 전에 한 번 더 확인해주세요."
    });
  } else if (compliance?.status === "pass") {
    items.push({
      id: "compliance",
      label: "광고 표현 확인",
      status: "pass",
      message: compliance.summary || "광고 표현 기준을 통과했어요."
    });
  }

  return items;
}

export function resolveResultArtifact(job: GenerationJob | null | undefined): ResultArtifactPayload | null {
  return getResultArtifactPayload(job);
}

export function getDisplayImageUrl(payload: ResultArtifactPayload | null | undefined): string | null {
  return firstPublicUrl(
    payload?.final_image_url,
    payload?.preview_image_url,
    payload?.copy_visual_preview_url,
    payload?.download_url
  );
}

export function getDownloadUrl(payload: ResultArtifactPayload | null | undefined): string | null {
  return firstPublicUrl(
    payload?.download_url,
    payload?.final_image_url,
    payload?.preview_image_url,
    payload?.copy_visual_preview_url
  );
}

export function resolvePreviewImageUrl(job: GenerationJob | null | undefined): string | null {
  return getDisplayImageUrl(getResultArtifactPayload(job));
}

export function resolveDownloadUrl(job: GenerationJob | null | undefined): string | null {
  return getDownloadUrl(getResultArtifactPayload(job));
}

export function hasOnlyLocalArtifactPath(payload: ResultArtifactPayload | null | undefined): boolean {
  if (!payload) {
    return false;
  }
  const publicUrl = getDisplayImageUrl(payload) ?? getDownloadUrl(payload);
  const localPaths = [
    payload.final_image_path,
    payload.download_path,
    payload.background_image_path,
    payload.copy_visual_preview_path,
    payload.output_dir
  ].filter(Boolean);
  return !publicUrl && localPaths.some((value) => isLocalArtifactPath(String(value)));
}

export function shouldEnableDownload(payload: ResultArtifactPayload | null | undefined): boolean {
  return Boolean(getDownloadUrl(payload));
}

export function shouldShowImagePreview(payload: ResultArtifactPayload | null | undefined): boolean {
  return Boolean(getDisplayImageUrl(payload));
}

export function isDownloadEnabled(job: GenerationJob | null | undefined): boolean {
  return shouldEnableDownload(getResultArtifactPayload(job));
}

export function buildGenerationResultCopyText(job: GenerationJob): string {
  const artifact = job.result_payload ?? {};
  const metadata = job.metadata ?? {};
  const engine = safeString(artifact.engine ?? metadata.engine);
  const renderMode = safeString(artifact.render_mode ?? metadata.execution_mode);
  const requestedRunMode = safeString(metadata.requested_run_mode);
  const effectiveRunMode = safeString(metadata.effective_run_mode);
  const displayUrl = getDisplayImageUrl(artifact);
  const downloadUrl = getDownloadUrl(artifact);
  const lines = [
    `Job ID: ${job.job_id}`,
    `Status: ${job.status}`,
    engine ? `Engine: ${engine}` : null,
    renderMode ? `Render mode: ${renderMode}` : null,
    requestedRunMode ? `Requested run mode: ${requestedRunMode}` : null,
    effectiveRunMode ? `Effective run mode: ${effectiveRunMode}` : null,
    `Image URL: ${displayUrl ?? "not available yet"}`,
    `Download URL: ${downloadUrl ?? "not available yet"}`,
    summaryLine("Prompt summary", artifact.prompt_summary),
    summaryLine("Validation", artifact.validation_summary),
    summaryLine("Copy summary", artifact.copy_summary),
    summaryLine("Layout summary", artifact.layout_summary),
    summaryLine("Render summary", artifact.render_summary),
    warningLine(artifact.validation_summary)
  ].filter((line): line is string => Boolean(line));
  return lines.join("\n");
}

export function getGenerationResultNotice(job: GenerationJob | null | undefined): {
  level: "info" | "success" | "warning" | "error";
  message: string;
} {
  if (!job) {
    return { level: "info", message: "아직 확인할 생성 결과가 없어요." };
  }
  if (job.status === "failed") {
    return { level: "error", message: getErrorMessage(job.error) ?? "이미지 생성에 실패했어요." };
  }
  if (job.status === "queued" || job.status === "running") {
    return { level: "info", message: "이미지를 생성하고 있어요." };
  }
  if (job.status === "done") {
    const payload = getResultArtifactPayload(job);
    if (!payload) {
      return { level: "warning", message: "생성은 끝났지만 결과 정보를 아직 확인할 수 없어요." };
    }
    const qualityDecision = safeString(payload.qualityDecision);
    if (payload.qualityRejected || qualityDecision === "reject" || payload.compliance?.status === "blocked") {
      return { level: "error", message: "검수에서 사용할 수 없는 결과로 판단됐어요." };
    }
    if (
      payload.requiresManualReview ||
      ["manual_review", "unavailable", "retry_image", "retry_layout"].includes(qualityDecision ?? "") ||
      payload.compliance?.status === "needs_review"
    ) {
      return { level: "warning", message: "사용 전에 결과를 한 번 더 확인해야 해요." };
    }
    if (shouldShowImagePreview(payload)) {
      return { level: "success", message: "완성된 이미지를 확인할 수 있어요." };
    }
    if (hasOnlyLocalArtifactPath(payload)) {
      return { level: "warning", message: "이미지는 생성됐지만 보관함에서 확인할 수 있는 주소가 아직 연결되지 않았어요." };
    }
    return { level: "warning", message: "생성은 끝났지만 표시할 이미지 정보를 찾지 못했어요." };
  }
  return { level: "info", message: "이미지 생성 상태를 확인하는 중이에요." };
}

export async function copyGenerationResultToClipboard(job: GenerationJob): Promise<boolean> {
  const text = buildGenerationResultCopyText(job);
  if (!globalThis.navigator?.clipboard?.writeText) {
    return false;
  }
  try {
    await globalThis.navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function validationItem(
  id: ValidationFeedbackItem["id"],
  label: string,
  report: unknown,
  messages: Record<ValidationFeedbackStatus, string>
): ValidationFeedbackItem | null {
  if (!report || typeof report !== "object" || Array.isArray(report)) {
    return null;
  }
  const status = validationStatus(report as Record<string, unknown>);
  return {
    id,
    label,
    status,
    message: messages[status]
  };
}

function validationStatus(report: Record<string, unknown>): ValidationFeedbackStatus {
  if (report.status === "fail" || report.status === "failed" || report.overall_pass === false) {
    return "fail";
  }
  if (
    report.status === "warn" ||
    hasNonEmptyArray(report.warnings) ||
    hasNonEmptyArray(report.issues) ||
    hasNonEmptyArray(report.bbox_issues) ||
    hasPositiveNumber(report.failed_slot_count)
  ) {
    return "warn";
  }
  if (report.status === "pass" || report.status === "passed" || report.overall_pass === true) {
    return "pass";
  }
  return "warn";
}

function hasNonEmptyArray(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0;
}

function hasPositiveNumber(value: unknown): boolean {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function firstPublicUrl(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    if (value && isPublicBrowserUrl(value)) {
      return value;
    }
  }
  return null;
}

function isPublicBrowserUrl(value: string): boolean {
  const normalized = value.trim();
  if (!normalized || isLocalArtifactPath(normalized)) {
    return false;
  }
  return /^https?:\/\//.test(normalized) || normalized.startsWith("/api/") || normalized.startsWith("/generated/");
}

function isLocalArtifactPath(value: string): boolean {
  const normalized = value.replace(/\\/g, "/").trim();
  if (/^[a-zA-Z]:\//.test(normalized)) {
    return true;
  }
  return LOCAL_PATH_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

function safeString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function summaryLine(label: string, value: Record<string, unknown> | null | undefined): string | null {
  const summary = sanitizeSummary(value);
  if (!summary) {
    return null;
  }
  return `${label}: ${JSON.stringify(summary)}`;
}

function warningLine(value: Record<string, unknown> | null | undefined): string | null {
  const warnings = value?.warnings;
  if (!Array.isArray(warnings) || warnings.length === 0) {
    return null;
  }
  return `Warnings: ${warnings.map((item) => String(item)).slice(0, 5).join(", ")}`;
}

function sanitizeSummary(value: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  if (!value) {
    return null;
  }
  const sanitized = sanitizeUnknown(value);
  return sanitized && typeof sanitized === "object" && !Array.isArray(sanitized)
    ? sanitized as Record<string, unknown>
    : null;
}

function sanitizeUnknown(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.slice(0, 20).map(sanitizeUnknown);
  }
  if (value && typeof value === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, rawValue] of Object.entries(value as Record<string, unknown>)) {
      if (isBlockedSummaryKey(key)) {
        continue;
      }
      const sanitized = sanitizeUnknown(rawValue);
      if (sanitized !== null && sanitized !== undefined) {
        output[key] = sanitized;
      }
    }
    return Object.keys(output).length ? output : null;
  }
  if (typeof value === "string") {
    return isLocalArtifactPath(value) ? "local artifact path hidden" : truncate(value, 160);
  }
  return value;
}

function isBlockedSummaryKey(key: string): boolean {
  return /(secret|token|api[_-]?key|raw_prompt|chain[_-]?of[_-]?thought|hidden[_-]?reasoning|raw[_-]?reasoning|prompt)$/i.test(key);
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}...` : value;
}

function getErrorMessage(error: unknown): string | null {
  if (!error || typeof error !== "object") {
    return typeof error === "string" ? error : null;
  }
  const maybe = error as { message?: unknown; error_code?: unknown };
  if (typeof maybe.message === "string") {
    return typeof maybe.error_code === "string" ? `${maybe.error_code}: ${maybe.message}` : maybe.message;
  }
  return typeof maybe.error_code === "string" ? maybe.error_code : null;
}
