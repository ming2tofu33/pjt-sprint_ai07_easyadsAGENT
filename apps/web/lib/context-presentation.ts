import type { InferredContext } from "@/types/marketing";

const CONTEXT_DISPLAY_LABELS: Record<string, string> = {
  beauty_nail: "네일샵",
  beauty_salon: "뷰티/미용",
  brand_awareness: "브랜드 인지도",
  cafe: "카페",
  discount_event: "할인 이벤트",
  new_launch: "신메뉴/신상품 출시",
  reservation_cta: "예약/방문 유도",
  restaurant: "외식업/식당",
  retention: "재방문 유도",
  review_event: "리뷰 이벤트",
  seasonal_limited: "시즌 한정 홍보",
  store: "일반 매장/판매",
};

const CAMPAIGN_INTENT_LABELS: Record<string, string> = {
  brand_awareness: "브랜드 인지도",
  business_introduction: "매장 소개",
  grand_opening: "그랜드 오픈 홍보",
  local_business_promotion: "매장 홍보",
  organization_promotion: "기관 홍보",
  product_promotion: "상품 홍보",
  store_opening: "신규 오픈 홍보",
  student_recruitment: "수강생 모집",
};

export function campaignIntentLabel(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return CAMPAIGN_INTENT_LABELS[value] ?? value;
}

export function displayContextValue(value: string | null | undefined): string | undefined {
  if (!value) {
    return undefined;
  }
  return CONTEXT_DISPLAY_LABELS[value] ?? campaignIntentLabel(value) ?? value;
}

export function contextItemSummary(context: InferredContext): string | null {
  return context.itemOrService || context.advertisedSubject || null;
}

export function contextPurposeSummary(context: InferredContext): string | null {
  return context.promotionGoal || campaignIntentLabel(context.campaignIntent) || null;
}
