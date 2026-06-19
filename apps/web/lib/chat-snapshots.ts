import type { ChatTurnResponse, GenerationJob } from "@/lib/api-client";
import type { DashboardSurface } from "@/lib/dashboard-navigation";
import type { GeneratedCreativeSnapshot } from "@/lib/generated-creative-storage";
import type { ImageGenerationEngine } from "@/lib/generation-engine";
import type { CopyGenerationMode } from "@/types/marketing";

export type ChatFlowSnapshot = GeneratedCreativeSnapshot;

export type ChatTurnSnapshot = {
  prompt: string;
  response?: ChatTurnResponse | null;
  generationJob?: GenerationJob | null;
  copyGenerationMode?: CopyGenerationMode;
  imageGenerationEngine?: ImageGenerationEngine;
  sourceAssetId?: string | null;
  referenceAssetId?: string | null;
  selectedReferenceTemplateId?: string | null;
  selectedReferenceTemplateTitle?: string | null;
  userCustomHeadline?: string | null;
  userCustomSubcopy?: string | null;
};

export type ChatGenerationFailureSnapshot = {
  message: string;
  threadId?: string | null;
  userInput?: string | null;
  imageGenerationEngine?: ImageGenerationEngine | null;
};

export const CHAT_FLOW_SNAPSHOT_STORAGE_KEY = "easyads_chat_flow_snapshot_v1";
export const CHAT_TURN_SNAPSHOT_STORAGE_KEY = "easyads_chat_turn_snapshot_v1";
export const CHAT_GENERATION_FAILURE_STORAGE_KEY = "easyads_chat_generation_failure_v1";
export const CHAT_FLOW_BACK_TARGET_STORAGE_KEY = "easyads_chat_flow_back_target_v1";

const CHAT_FLOW_BACK_TARGETS = new Set(["home", "studio", "reference", "ads", "my", "brand", "photo"]);

function safeSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readJsonSnapshot<T>(key: string): T | null {
  const storage = safeSessionStorage();
  if (!storage) {
    return null;
  }
  const raw = storage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function writeJsonSnapshot<T>(key: string, value: T): void {
  const storage = safeSessionStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // Navigation should still work if sessionStorage is unavailable.
  }
}

export function clearJsonSnapshot(key: string): void {
  const storage = safeSessionStorage();
  if (!storage) {
    return;
  }
  try {
    storage.removeItem(key);
  } catch {
    // Ignore storage failures.
  }
}

function readStringSnapshot(key: string): string | null {
  const storage = safeSessionStorage();
  if (!storage) {
    return null;
  }
  return storage.getItem(key);
}

function writeStringSnapshot(key: string, value: string): void {
  const storage = safeSessionStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(key, value);
  } catch {
    // Navigation should still work if sessionStorage is unavailable.
  }
}

export function readChatFlowSnapshot(): ChatFlowSnapshot | null {
  return readJsonSnapshot<ChatFlowSnapshot>(CHAT_FLOW_SNAPSHOT_STORAGE_KEY);
}

export function writeChatFlowSnapshot(snapshot: ChatFlowSnapshot): void {
  writeJsonSnapshot(CHAT_FLOW_SNAPSHOT_STORAGE_KEY, snapshot);
}

export function clearChatFlowSnapshot(): void {
  clearJsonSnapshot(CHAT_FLOW_SNAPSHOT_STORAGE_KEY);
}

export function readChatTurnSnapshot(): ChatTurnSnapshot | null {
  return readJsonSnapshot<ChatTurnSnapshot>(CHAT_TURN_SNAPSHOT_STORAGE_KEY);
}

export function writeChatTurnSnapshot(snapshot: ChatTurnSnapshot): void {
  writeJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY, snapshot);
}

export function clearChatTurnSnapshot(): void {
  clearJsonSnapshot(CHAT_TURN_SNAPSHOT_STORAGE_KEY);
}

export function readGenerationFailureSnapshot(): ChatGenerationFailureSnapshot | null {
  return readJsonSnapshot<ChatGenerationFailureSnapshot>(CHAT_GENERATION_FAILURE_STORAGE_KEY);
}

export function writeGenerationFailureSnapshot(snapshot: ChatGenerationFailureSnapshot): void {
  writeJsonSnapshot(CHAT_GENERATION_FAILURE_STORAGE_KEY, snapshot);
}

export function clearGenerationFailureSnapshot(): void {
  clearJsonSnapshot(CHAT_GENERATION_FAILURE_STORAGE_KEY);
}

export function isChatFlowBackTarget(value: string | null | undefined): value is DashboardSurface {
  return Boolean(value && CHAT_FLOW_BACK_TARGETS.has(value));
}

export function readChatFlowBackTarget(): DashboardSurface | null {
  const raw = readStringSnapshot(CHAT_FLOW_BACK_TARGET_STORAGE_KEY);
  return isChatFlowBackTarget(raw) ? raw : null;
}

export function writeChatFlowBackTarget(surface: DashboardSurface): void {
  if (!isChatFlowBackTarget(surface)) {
    return;
  }
  writeStringSnapshot(CHAT_FLOW_BACK_TARGET_STORAGE_KEY, surface);
}
