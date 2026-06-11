import type { GenerationJob } from "./api-client";
import type { CopyCandidateOrigin, CopyOption, OptionQuestion } from "@/types/marketing";

export type GenerationJobPendingInterrupt = {
  type?: string;
  option_question?: OptionQuestion;
  [key: string]: unknown;
};

export type GenerationJobCustomCopyField = {
  field: "user_custom_headline" | "user_custom_subcopy" | string;
  label: string;
  placeholder: string;
  required: boolean;
  maxRecommendedChars?: number | null;
};

export type ComplianceAction = {
  id: "use_suggestion" | "edit_manually" | "submit_claim" | "keep_original_draft" | "cancel" | string;
  label: string;
  available: boolean;
};

export type ComplianceFindingFE = {
  finding_id?: string | null;
  field?: string | null;
  matched_text?: string | null;
  severity?: "warn" | "evidence_required" | "block" | string | null;
  reason?: string | null;
  suggested_text?: string | null;
  legal_basis?: { key?: string; law_name?: string; article?: string; summary?: string }[];
  evidence_requirements?: string[];
  hitl_question?: string | null;
};

export type ParsedGenerationJobInterrupt =
  | {
      type: "option_question";
      optionQuestion: OptionQuestion;
      raw: GenerationJobPendingInterrupt;
    }
  | {
      type: "copy_candidate_selection";
      candidates: CopyOption[];
      recommendedCandidateId?: string | null;
      copyCandidateOrigin: CopyCandidateOrigin;
      raw: GenerationJobPendingInterrupt;
    }
  | {
      type: "custom_copy_input";
      fields: GenerationJobCustomCopyField[];
      raw: GenerationJobPendingInterrupt;
    }
  | {
      type: "copy_compliance_review";
      status: string;
      summary: string;
      findings: ComplianceFindingFE[];
      actions: ComplianceAction[];
      raw: GenerationJobPendingInterrupt;
    }
  | {
      type: "unsupported";
      rawType?: string | null;
      raw: GenerationJobPendingInterrupt;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asCopyCandidateOrigin(value: unknown): CopyCandidateOrigin {
  return value === "llm" || value === "rule_based" || value === "fallback" || value === "unknown" ? value : "unknown";
}

function normalizeCandidateMetadata(raw: unknown): CopyOption["metadata"] | undefined {
  if (!isRecord(raw)) {
    return undefined;
  }
  const metadata: NonNullable<CopyOption["metadata"]> = { ...raw };
  const compliance = raw.compliance;
  if (isRecord(compliance)) {
    metadata.compliance = {
      ...compliance,
      status: asString(compliance.status) ?? null,
      finding_count: asNumber(compliance.finding_count ?? compliance.findingCount),
      disabled: asBoolean(compliance.disabled)
    };
  }
  return metadata;
}

function normalizeCandidate(raw: unknown, index: number): CopyOption | null {
  if (!isRecord(raw)) {
    return null;
  }
  const headline = asString(raw.headline) ?? asString(raw.title) ?? asString(raw.copy);
  if (!headline) {
    return null;
  }
  const metadata = normalizeCandidateMetadata(raw.metadata);
  return {
    id: asString(raw.id) ?? `copy_${index + 1}`,
    headline,
    subcopy: asString(raw.subcopy) ?? asString(raw.body) ?? null,
    cta: asString(raw.cta) ?? null,
    ...(metadata ? { metadata } : {})
  };
}

function labelForCustomCopyField(field: string): string {
  if (field === "user_custom_headline" || field === "headline") {
    return "메인 문구";
  }
  if (field === "user_custom_subcopy" || field === "subcopy") {
    return "보조 문구";
  }
  return "추가 문구";
}

function normalizeCustomCopyField(raw: unknown): GenerationJobCustomCopyField | null {
  if (typeof raw === "string") {
    const field = raw === "headline" ? "user_custom_headline" : raw === "subcopy" ? "user_custom_subcopy" : raw;
    return {
      field,
      label: labelForCustomCopyField(field),
      placeholder: field === "user_custom_headline" ? "광고에 넣을 메인 문구" : "이벤트 상세나 보조 문구",
      required: field === "user_custom_headline"
    };
  }
  if (!isRecord(raw)) {
    return null;
  }
  const field = asString(raw.field);
  if (!field) {
    return null;
  }
  return {
    field,
    label: labelForCustomCopyField(field),
    placeholder: asString(raw.placeholder) ?? (field === "user_custom_headline" ? "광고에 넣을 메인 문구" : "이벤트 상세나 보조 문구"),
    required: asBoolean(raw.required, field === "user_custom_headline"),
    maxRecommendedChars: asNumber(raw.max_recommended_chars)
  };
}

export function parseGenerationJobInterrupt(raw: unknown): ParsedGenerationJobInterrupt | null {
  if (!isRecord(raw)) {
    return null;
  }
  const interrupt = raw as GenerationJobPendingInterrupt;
  if (interrupt.type === "option_question" && interrupt.option_question) {
    return {
      type: "option_question",
      optionQuestion: interrupt.option_question,
      raw: interrupt
    };
  }
  if (interrupt.type === "copy_candidate_selection") {
    const candidates = Array.isArray(interrupt.candidates)
      ? interrupt.candidates.map(normalizeCandidate).filter((candidate): candidate is CopyOption => Boolean(candidate))
      : [];
    const metadata = isRecord(interrupt.metadata) ? interrupt.metadata : {};
    return {
      type: "copy_candidate_selection",
      candidates,
      recommendedCandidateId: asString(interrupt.recommended_candidate_id) ?? candidates[0]?.id ?? null,
      copyCandidateOrigin: asCopyCandidateOrigin(interrupt.copy_candidate_origin ?? interrupt.copyCandidateOrigin ?? metadata.copy_candidate_origin ?? metadata.copyCandidateOrigin),
      raw: interrupt
    };
  }
  if (interrupt.type === "custom_copy_input") {
    const fields = Array.isArray(interrupt.fields)
      ? interrupt.fields
          .map(normalizeCustomCopyField)
          .filter((field): field is GenerationJobCustomCopyField => Boolean(field))
      : [];
    return {
      type: "custom_copy_input",
      fields,
      raw: interrupt
    };
  }
  if (interrupt.type === "copy_compliance_review") {
    const findings: ComplianceFindingFE[] = Array.isArray(interrupt.findings)
      ? (interrupt.findings as unknown[]).filter((f): f is ComplianceFindingFE => Boolean(f) && typeof f === "object")
      : [];
    const actions: ComplianceAction[] = Array.isArray(interrupt.actions)
      ? (interrupt.actions as unknown[]).filter((a): a is ComplianceAction => Boolean(a) && typeof a === "object")
      : [];
    return {
      type: "copy_compliance_review",
      status: asString(interrupt.status) ?? "evidence_required",
      summary: asString(interrupt.summary) ?? "광고 규제 확인이 필요합니다.",
      findings,
      actions,
      raw: interrupt
    };
  }
  return {
    type: "unsupported",
    rawType: asString(interrupt.type) ?? null,
    raw: interrupt
  };
}

export function getPendingGenerationJobParsedInterrupt(job: GenerationJob | null | undefined): ParsedGenerationJobInterrupt | null {
  if (job?.status !== "waiting_user_input") {
    return null;
  }
  return parseGenerationJobInterrupt(getPendingGenerationJobInterrupt(job));
}

export function getPendingGenerationJobOptionQuestion(job: GenerationJob | null | undefined): OptionQuestion | null {
  const interrupt = getPendingGenerationJobParsedInterrupt(job);
  if (interrupt?.type !== "option_question") {
    return null;
  }
  return interrupt.optionQuestion;
}
