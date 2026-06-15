import type { ArchiveItem } from "@/lib/api-client";
import type { MockCreative } from "@/lib/mock-dashboard-data";

function metadataString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

function metadataList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function normalizeFileType(value: unknown): "PNG" | "JPG" {
  const fileType = metadataString(value)?.toUpperCase();
  return fileType === "JPG" ? "JPG" : "PNG";
}

export function archiveItemToCreative(item: ArchiveItem): MockCreative | null {
  const imageUrl = item.thumbnailUrl || item.imageUrl || item.downloadUrl;
  if (!imageUrl) {
    return null;
  }

  const subtitle =
    metadataString(item.metadata?.subtitle) ||
    [item.platform, item.adFormat].filter(Boolean).join(" · ") ||
    "저장한 광고";

  return {
    id: item.adId,
    jobId: item.jobId,
    outputId: item.outputId,
    title: item.title,
    subtitle,
    format: item.adFormat || item.platform || "이미지",
    imageUrl,
    date: item.savedAt || item.createdAt || "저장됨",
    tone: "mint",
    badge: "보관함",
    status: item.status === "favorite" ? "favorite" : "saved",
    channel: item.platform || item.adFormat || "광고",
    fileName: metadataString(item.metadata?.fileName) || "saved-creative.png",
    fileType: normalizeFileType(item.metadata?.fileType),
    storage: "내 광고 보관함",
    savedAt: item.savedAt || item.createdAt || "저장됨",
    tags: metadataList(item.metadata?.tags)
  };
}
