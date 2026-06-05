import {
  brandKitMeta,
  brandKitPhrases,
  brandKitProducts,
  brandKitTone,
  readSavedBrandKit,
  type StoredBrandKit
} from "@/lib/brand-kit-storage";

export const GENERATION_DRAFT_PROMPT_STORAGE_KEY = "easyads_generation_draft_prompt_v1";
export const GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY = "easyads_generation_draft_reference_template_v1";
const GENERATION_REQUEST_CONTEXT_STORAGE_KEY = "easyads_generation_request_context_v1";

export type GenerationRequestContext = {
  selectedReferenceTemplateId?: string;
  selectedReferenceTemplateTitle?: string;
  draftPrompt?: string;
  source?: "reference_gallery" | "manual" | "unknown";
};

function storage(): Storage | null {
  try {
    if (typeof window === "undefined") {
      return null;
    }
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function compactLines(lines: string[]): string {
  return lines.map((line) => line.trim()).filter(Boolean).join("\n");
}

export function buildBrandKitGenerationContext(brandKit: StoredBrandKit | null): string {
  if (!brandKit) {
    return "";
  }

  return compactLines([
    "[브랜드 파일]",
    `가게 이름: ${brandKit.businessName}`,
    `가게 정보: ${brandKitMeta(brandKit)}`,
    `브랜드 톤: ${brandKitTone(brandKit)}`,
    `대표 상품/서비스: ${brandKitProducts(brandKit)}`,
    `자주 쓰는 문구: ${brandKitPhrases(brandKit)}`,
    "[/브랜드 파일]"
  ]);
}

export function appendSavedBrandKitContext(prompt: string): string {
  const trimmedPrompt = prompt.trim();
  const context = buildBrandKitGenerationContext(readSavedBrandKit());
  return context ? `${trimmedPrompt}\n\n${context}` : trimmedPrompt;
}

export function writeGenerationDraftPrompt(prompt: string) {
  try {
    storage()?.setItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY, prompt.trim());
  } catch {
    // The user can still type manually if sessionStorage is unavailable.
  }
}

export function writeGenerationDraftReferenceTemplateId(templateId: string) {
  try {
    storage()?.setItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY, templateId.trim());
  } catch {
    // The generation flow can still continue without a reference template.
  }
}

export function saveGenerationRequestContext(context: GenerationRequestContext): void {
  try {
    storage()?.setItem(GENERATION_REQUEST_CONTEXT_STORAGE_KEY, JSON.stringify(context));
    if (context.draftPrompt) {
      writeGenerationDraftPrompt(context.draftPrompt);
    }
    if (context.selectedReferenceTemplateId) {
      writeGenerationDraftReferenceTemplateId(context.selectedReferenceTemplateId);
    }
  } catch {
    // Generation can continue without persisted request context.
  }
}

export function readGenerationRequestContext(): GenerationRequestContext | null {
  try {
    const raw = storage()?.getItem(GENERATION_REQUEST_CONTEXT_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as GenerationRequestContext) : null;
  } catch {
    return null;
  }
}

export function readGenerationDraftPrompt(): string {
  try {
    const draftPrompt = storage()?.getItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY);
    if (draftPrompt) {
      return draftPrompt;
    }
    return readGenerationRequestContext()?.draftPrompt ?? "";
  } catch {
    return "";
  }
}

export function readGenerationDraftReferenceTemplateId(): string {
  try {
    const templateId = storage()?.getItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY);
    if (templateId) {
      return templateId;
    }
    return readGenerationRequestContext()?.selectedReferenceTemplateId ?? "";
  } catch {
    return "";
  }
}

export function clearGenerationRequestContext(): void {
  try {
    storage()?.removeItem(GENERATION_REQUEST_CONTEXT_STORAGE_KEY);
  } catch {
    // Ignore unavailable storage.
  }
}

export function clearGenerationDraftPrompt() {
  try {
    storage()?.removeItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY);
    storage()?.removeItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY);
    storage()?.removeItem(GENERATION_REQUEST_CONTEXT_STORAGE_KEY);
  } catch {
    // Ignore storage failures; a fresh chat can still continue.
  }
}
