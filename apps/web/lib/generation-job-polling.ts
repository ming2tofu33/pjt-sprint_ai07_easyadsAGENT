import type { GenerationJob } from "@/lib/api-client";

export type PollingDecision = {
  shouldContinue: boolean;
  delayMs: number;
  reason: string;
};

export const MAX_CONSECUTIVE_POLL_ERRORS = 5;

function normalized(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function isWaitingGenerationJob(job: GenerationJob): boolean {
  const status = normalized(job.status);
  const stage = normalized(job.progress?.current_stage ?? job.current_stage);
  return status === "waiting_user_input" || stage === "waiting_user_input";
}

export function isTerminalGenerationJob(job: GenerationJob): boolean {
  const terminal = ["done", "completed", "failed", "cancelled"];
  const status = normalized(job.status);
  const stage = normalized(job.progress?.current_stage ?? job.current_stage);
  return terminal.includes(status) || terminal.includes(stage);
}

export function isFailedGenerationJob(job: GenerationJob): boolean {
  const failed = ["failed", "cancelled"];
  const status = normalized(job.status);
  const stage = normalized(job.progress?.current_stage ?? job.current_stage);
  return failed.includes(status) || failed.includes(stage);
}

export function getGenerationJobPollingDecision(input: {
  job: GenerationJob;
  attempt: number;
  consecutiveErrors: number;
  documentHidden: boolean;
}): PollingDecision {
  const status = normalized(input.job.status);
  const stage = normalized(input.job.progress?.current_stage ?? input.job.current_stage);

  if (isTerminalGenerationJob(input.job)) {
    return { shouldContinue: false, delayMs: 0, reason: `terminal_${status}` };
  }
  if (isWaitingGenerationJob(input.job)) {
    return { shouldContinue: false, delayMs: 0, reason: "waiting_user_input" };
  }
  if (input.consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) {
    return { shouldContinue: false, delayMs: 0, reason: "network_error_limit" };
  }
  if (input.documentHidden) {
    return { shouldContinue: true, delayMs: 10000, reason: "document_hidden" };
  }
  if (input.consecutiveErrors > 0) {
    return {
      shouldContinue: true,
      delayMs: Math.min(8000, 1000 * 2 ** (input.consecutiveErrors - 1)),
      reason: "network_backoff"
    };
  }
  if (["queued", "validating", "planning"].includes(status) || ["queued", "validating", "planning"].includes(stage)) {
    return { shouldContinue: true, delayMs: 900, reason: "early_stage" };
  }
  if (["rendering", "validating_output"].includes(stage)) {
    return { shouldContinue: true, delayMs: 1500, reason: "output_stage" };
  }
  if (stage.includes("generat") || stage.includes("modal") || stage.includes("t2i")) {
    return { shouldContinue: true, delayMs: input.attempt >= 4 ? 4000 : 2200, reason: "generating_stage" };
  }
  return { shouldContinue: true, delayMs: 1800, reason: "running_default" };
}

export function withPollingJitter(delayMs: number, random: () => number = Math.random): number {
  if (delayMs <= 0) {
    return 0;
  }
  const ratio = 0.2;
  const jittered = Math.round(delayMs * (1 - ratio / 2 + random() * ratio));
  return Math.max(100, Math.min(15000, jittered));
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}
