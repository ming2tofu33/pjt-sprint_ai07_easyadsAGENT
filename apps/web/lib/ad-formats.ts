export const CHANNEL_IDS = ["instagram-feed", "instagram-story", "poster", "flyer", "banner", "product_detail"] as const;

export type ChannelId = (typeof CHANNEL_IDS)[number];

export const channelOptions = [
  { id: "instagram-feed", label: "인스타 피드", ratio: "1:1" },
  { id: "instagram-story", label: "인스타 스토리", ratio: "9:16" },
  { id: "poster", label: "포스터", ratio: "4:5" },
  { id: "flyer", label: "전단지", ratio: "A4" },
  { id: "banner", label: "배너", ratio: "16:9" },
  { id: "product_detail", label: "상세페이지", ratio: "가로형" }
 ] as const satisfies ReadonlyArray<{ id: ChannelId; label: string; ratio: string }>;

export const AD_FORMAT_BY_CHANNEL_ID: Record<ChannelId, string> = {
  "instagram-feed": "instagram_feed",
  "instagram-story": "instagram_story",
  poster: "poster",
  flyer: "flyer",
  banner: "banner",
  product_detail: "product_detail"
};

export const CHANNEL_ID_BY_AD_FORMAT: Record<string, ChannelId> = Object.fromEntries(
  Object.entries(AD_FORMAT_BY_CHANNEL_ID).map(([channelId, adFormat]) => [adFormat, channelId])
) as Record<string, ChannelId>;

export function normalizeSelectedChannelId(value: string | null | undefined): ChannelId | null {
  const normalized = value?.trim();
  if (!normalized) {
    return null;
  }
  if (CHANNEL_IDS.includes(normalized as ChannelId)) {
    return normalized as ChannelId;
  }
  return CHANNEL_ID_BY_AD_FORMAT[normalized] ?? null;
}

export function toCanonicalAdFormat(value: string | null | undefined): string | undefined {
  const channelId = normalizeSelectedChannelId(value);
  return channelId ? AD_FORMAT_BY_CHANNEL_ID[channelId] : undefined;
}
