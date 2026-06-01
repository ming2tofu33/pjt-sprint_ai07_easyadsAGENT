export type GenerationRequestContext = {
  selectedReferenceTemplateId?: string;
  selectedReferenceTemplateTitle?: string;
  draftPrompt?: string;
  source?: "reference_gallery" | "manual" | "unknown";
};

const STORAGE_KEY = "easyads_generation_request_context_v1";

function storage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.sessionStorage ?? null;
}

export function saveGenerationRequestContext(context: GenerationRequestContext): void {
  try {
    storage()?.setItem(STORAGE_KEY, JSON.stringify(context));
  } catch {
    // Generation can continue without persisted request context.
  }
}

export function readGenerationRequestContext(): GenerationRequestContext | null {
  try {
    const raw = storage()?.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as GenerationRequestContext) : null;
  } catch {
    return null;
  }
}

export function clearGenerationRequestContext(): void {
  try {
    storage()?.removeItem(STORAGE_KEY);
  } catch {
    // Ignore unavailable storage.
  }
}
