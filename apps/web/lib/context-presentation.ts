import type { InferredContext } from "@/types/marketing";

const CONTEXT_DISPLAY_LABELS: Record<string, string> = {
  beauty_nail: "네일",
  beauty_salon: "뷰티/미용",
  brand_awareness: "브랜드 인지도",
  cafe: "카페",
  discount_event: "할인 이벤트",
  new_launch: "신메뉴/신상품 출시",
  new_menu_launch: "신메뉴 출시",
  new_product_launch: "신상품 출시",
  reservation_cta: "예약/방문 유도",
  restaurant: "음식점/식당",
  retention: "재방문 유도",
  review_event: "리뷰 이벤트",
  seasonal_limited: "시즌 한정 홍보",
  store: "일반 매장/소매",
  store_opening: "신규 오픈 홍보",
  service_launch: "신규 서비스 시작",
};

const CAMPAIGN_INTENT_LABELS: Record<string, string> = {
  brand_awareness: "\ube0c\ub79c\ub4dc \uc778\uc9c0\ub3c4",
  business_introduction: "\ub9e4\uc7a5 \uc18c\uac1c",
  grand_opening: "\uadf8\ub79c\ub4dc \uc624\ud508 \ud64d\ubcf4",
  local_business_promotion: "\ub9e4\uc7a5 \ud64d\ubcf4",
  new_menu_launch: "\uc2e0\uba54\ub274 \ucd9c\uc2dc",
  new_product_launch: "\uc2e0\uc0c1\ud488 \ucd9c\uc2dc",
  organization_promotion: "\uae30\uad00 \ud64d\ubcf4",
  product_promotion: "\uc0c1\ud488 \ud64d\ubcf4",
  service_launch: "\uc2e0\uaddc \uc11c\ube44\uc2a4 \uc2dc\uc791",
  store_opening: "\uc2e0\uaddc \uc624\ud508 \ud64d\ubcf4",
  student_recruitment: "\uc218\uac15\uc0dd \ubaa8\uc9d1",
};

export function campaignIntentLabel(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return CAMPAIGN_INTENT_LABELS[value] ?? null;
}

export function displayContextValue(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  if (CONTEXT_DISPLAY_LABELS[value]) {
    return CONTEXT_DISPLAY_LABELS[value];
  }
  if (/^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$/.test(value)) {
    return undefined; // Hide unknown internal tokens
  }
  return value; // Pass through free-text (e.g. Korean user input or open domain words)
}

export function contextBusinessSummary(context: InferredContext): string | null {
  return displayContextValue(context.businessType) ?? null;
}

export function contextItemSummary(context: InferredContext): string | null {
  return context.itemOrService || context.advertisedSubject || null;
}

export function contextItemLabel(context: InferredContext): "\uc0c1\ud488/\uc11c\ube44\uc2a4" | "\uad11\uace0 \ub300\uc0c1" {
  if (context.itemOrService) {
    return "\uc0c1\ud488/\uc11c\ube44\uc2a4";
  }
  if (context.advertisedSubject) {
    return "\uad11\uace0 \ub300\uc0c1";
  }
  return "\uc0c1\ud488/\uc11c\ube44\uc2a4";
}

export function contextPurposeSummary(context: InferredContext): string | null {
  return displayContextValue(context.promotionGoal) ?? campaignIntentLabel(context.campaignIntent) ?? null;
}
