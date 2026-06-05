import type { GenerationJob } from "./api-client";
import type { OptionQuestion } from "@/types/marketing";

export type GenerationJobPendingInterrupt = {
  type?: string;
  option_question?: OptionQuestion;
  [key: string]: unknown;
};

export function getPendingGenerationJobInterrupt(job: GenerationJob | null | undefined): GenerationJobPendingInterrupt | null {
  const metadata = job?.metadata;
  const pending = metadata?.pending_interrupt;
  if (!pending || typeof pending !== "object" || Array.isArray(pending)) {
    return null;
  }
  return pending as GenerationJobPendingInterrupt;
}

export function hasPendingGenerationJobInterrupt(job: GenerationJob | null | undefined): boolean {
  return getPendingGenerationJobInterrupt(job) !== null;
}

export function getPendingGenerationJobOptionQuestion(job: GenerationJob | null | undefined): OptionQuestion | null {
  if (job?.status !== "waiting_user_input") {
    return null;
  }
  const interrupt = getPendingGenerationJobInterrupt(job);
  if (interrupt?.type !== "option_question") {
    return null;
  }
  return interrupt.option_question ?? null;
}
