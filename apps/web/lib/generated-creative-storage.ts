import { buildGeneratedAssetUrl } from "@/lib/generated-assets";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import type { ImageGenerationEngine } from "@/lib/generation-engine";
import type { ChatBrief, CopyCandidateOrigin, CopyCandidateSource, CopyOption, InferredContext } from "@/types/marketing";

export type GeneratedCreativeSnapshot = {
  prompt: string;
  jobId: string;
  threadId: string;
  context: InferredContext;
  copyCandidates: CopyOption[];
  copyCandidateSource?: CopyCandidateSource;
  copyCandidateOrigin?: CopyCandidateOrigin;
  selectedCopyId: string;
  selectedChannelId: string;
  selectedTone: string;
  customDirection: string;
  userCustomHeadline?: string | null;
  userCustomSubcopy?: string | null;
  brief: ChatBrief;
  selectedReferenceTemplateId?: string | null;
  selectedReferenceTemplateTitle?: string | null;
  imageGenerationEngine?: ImageGenerationEngine;
  sourceImagePath?: string | null;
  referenceImagePath?: string | null;
};

const GENERATED_CREATIVES_STORAGE_KEY = "easyads_generated_creatives_v1";

function resolveSnapshotImageUrl(snapshot: GeneratedCreativeSnapshot): string | null {
  return snapshot.brief.finalImageUrl || snapshot.brief.downloadUrl || buildGeneratedAssetUrl(snapshot.brief.finalImagePath);
}

function creativeFromSnapshot(snapshot: GeneratedCreativeSnapshot): MockCreative {
  const channelMatch = snapshot.brief.channel.match(/\(([^)]+)\)/);
  const imageUrl = resolveSnapshotImageUrl(snapshot);
  return {
    id: `generated-${snapshot.jobId}`,
    jobId: snapshot.jobId,
    title: snapshot.brief.copy,
    subtitle: `${snapshot.brief.item} · ${snapshot.brief.channel}`,
    format: channelMatch?.[1] ?? snapshot.brief.channel,
    imageUrl,
    date: "방금 생성",
    tone: "strawberry",
    badge: "실제 생성",
    status: "saved",
    channel: snapshot.brief.channel.replace(/\s*\(.+\)/, ""),
    fileName: "final_composite.png",
    fileType: "PNG",
    storage: "브라우저 임시 보관함",
    savedAt: "방금 생성",
    tags: [
      snapshot.context.businessType,
      snapshot.context.itemOrService,
      snapshot.context.promotionGoal,
      snapshot.brief.channel.replace(/\s*\(.+\)/, "")
    ].filter(Boolean)
  };
}

export function readGeneratedCreatives(): MockCreative[] {
  try {
    const raw = window.localStorage.getItem(GENERATED_CREATIVES_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MockCreative[]) : [];
  } catch {
    return [];
  }
}

export function addGeneratedCreativeSnapshot(snapshot: GeneratedCreativeSnapshot): MockCreative[] {
  if (!resolveSnapshotImageUrl(snapshot)) {
    return readGeneratedCreatives();
  }
  const creative = creativeFromSnapshot(snapshot);
  const existing = readGeneratedCreatives().filter((item) => item.id !== creative.id);
  const nextCreatives = [creative, ...existing].slice(0, 5);
  try {
    window.localStorage.setItem(GENERATED_CREATIVES_STORAGE_KEY, JSON.stringify(nextCreatives));
  } catch {
    // The generated result still stays available through the active chat snapshot.
  }
  return nextCreatives;
}

export function removeGeneratedCreative(creativeId: string): MockCreative[] {
  const nextCreatives = readGeneratedCreatives().filter((item) => item.id !== creativeId);
  try {
    window.localStorage.setItem(GENERATED_CREATIVES_STORAGE_KEY, JSON.stringify(nextCreatives));
  } catch {
    // Keep the in-memory UI update even if localStorage is unavailable.
  }
  return nextCreatives;
}
