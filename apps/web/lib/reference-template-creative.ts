import type { ReferenceTemplateCard } from "@/lib/api-client";
import type { CreativeTone, MockCreative } from "@/lib/mock-dashboard-data";

export function referenceTemplateImageUrl(template: ReferenceTemplateCard): string | null {
  return template.previewUrl ?? template.thumbnailUrl ?? null;
}

export function hasReferenceTemplateImage(template: ReferenceTemplateCard): boolean {
  return Boolean(referenceTemplateImageUrl(template));
}

export function referenceTemplateToCreative(template: ReferenceTemplateCard): MockCreative {
  return {
    id: template.templateId,
    title: template.title,
    subtitle: template.description ?? [formatReferenceTemplateLabel(template), ...template.tags.slice(0, 2)].filter(Boolean).join(" · "),
    format: formatReferenceTemplateLabel(template),
    imageUrl: referenceTemplateImageUrl(template),
    tone: toneForReferenceTemplate(template),
    badge: categoryLabel(template.category),
    tags: template.tags,
    savedCount: Math.round(template.popularityScore * 100),
    styleProfile: {
      colors: template.colorPalette.length > 0 ? template.colorPalette : ["#F7F4EF", "#111827", "#D1D5DB"],
      layout: template.layoutHint ?? "선택한 레퍼런스의 구도와 정보 배치를 참고해요.",
      copySpace: template.typographyHint ?? "문구가 잘 읽히는 위치와 크기를 참고해요.",
      mood: template.styleKeywords.join(", ") || categoryLabel(template.category),
      bestUse: [formatReferenceTemplateLabel(template), ...template.businessTypes].filter(Boolean).join(", ")
    }
  };
}

export function formatReferenceTemplateLabel(template: ReferenceTemplateCard): string {
  const format = template.adFormats[0] ?? template.aspectRatio ?? "reference";
  const labels: Record<string, string> = {
    instagram_feed: "인스타 피드",
    instagram_story: "인스타 스토리",
    poster: "포스터",
    flyer: "전단지",
    banner: "배너"
  };
  return labels[format] ?? format;
}

export function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    cafe: "카페",
    food: "음식",
    restaurant: "음식점",
    beauty: "뷰티",
    retail: "리테일",
    event: "이벤트",
    flyer: "전단지",
    banner: "배너",
    instagram_story: "스토리",
    instagram_feed: "피드"
  };
  return labels[category] ?? category;
}

function toneForReferenceTemplate(template: ReferenceTemplateCard): CreativeTone {
  const joined = [...template.styleKeywords, ...template.tags, template.category].join(" ").toLowerCase();
  if (joined.includes("mint") || joined.includes("clean") || joined.includes("green")) {
    return "mint";
  }
  if (joined.includes("yellow") || joined.includes("summer") || joined.includes("event")) {
    return "sunny";
  }
  if (joined.includes("purple") || joined.includes("premium") || joined.includes("minimal")) {
    return "cream";
  }
  if (joined.includes("strawberry") || joined.includes("pink") || joined.includes("dessert")) {
    return "strawberry";
  }
  return "peach";
}
