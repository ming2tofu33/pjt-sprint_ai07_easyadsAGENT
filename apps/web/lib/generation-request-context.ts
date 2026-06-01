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

function storage(): Storage | null {
  try {
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
    "[브랜드 키트]",
    `가게 이름: ${brandKit.businessName}`,
    `가게 정보: ${brandKitMeta(brandKit)}`,
    `브랜드 톤: ${brandKitTone(brandKit)}`,
    `대표 상품/서비스: ${brandKitProducts(brandKit)}`,
    `자주 쓰는 문구: ${brandKitPhrases(brandKit)}`,
    "[/브랜드 키트]"
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

export function readGenerationDraftPrompt(): string {
  try {
    return storage()?.getItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function readGenerationDraftReferenceTemplateId(): string {
  try {
    return storage()?.getItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function clearGenerationDraftPrompt() {
  try {
    storage()?.removeItem(GENERATION_DRAFT_PROMPT_STORAGE_KEY);
    storage()?.removeItem(GENERATION_DRAFT_REFERENCE_TEMPLATE_STORAGE_KEY);
  } catch {
    // Ignore storage failures; a fresh chat can still continue.
  }
}
