import type { GenerationJob, ResultArtifactPayload } from "./api-client";


export function resolveResultArtifact(job: GenerationJob | null | undefined): ResultArtifactPayload | null {
  return job?.result_payload ?? null;
}

export function resolvePreviewImageUrl(job: GenerationJob | null | undefined): string | null {
  const artifact = resolveResultArtifact(job);
  if (artifact?.final_image_url) {
    return artifact.final_image_url;
  }
  if (artifact?.download_url) {
    return artifact.download_url;
  }
  return null;
}

export function resolveDownloadUrl(job: GenerationJob | null | undefined): string | null {
  const artifact = resolveResultArtifact(job);
  return artifact?.download_url ?? artifact?.final_image_url ?? null;
}

export function isDownloadEnabled(job: GenerationJob | null | undefined): boolean {
  return Boolean(resolveDownloadUrl(job));
}

export function buildGenerationResultCopyText(job: GenerationJob): string {
  const artifact = job.result_payload ?? {};
  const lines = [
    `Job ID: ${job.job_id}`,
    `Status: ${job.status}`,
    `Engine: ${artifact.engine ?? job.metadata?.engine ?? "unknown"}`,
    `Render mode: ${artifact.render_mode ?? job.metadata?.execution_mode ?? "unknown"}`,
    `Final image path: ${artifact.final_image_path ?? job.output_path ?? "not available"}`,
    `Prompt summary: ${JSON.stringify(artifact.prompt_summary ?? {})}`,
    `Validation: ${JSON.stringify(artifact.validation_summary ?? {})}`,
    `Copy summary: ${JSON.stringify(artifact.copy_summary ?? {})}`,
    `Layout summary: ${JSON.stringify(artifact.layout_summary ?? {})}`
  ];
  return lines.join("\n");
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
