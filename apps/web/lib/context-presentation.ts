import type { InferredContext } from "@/types/marketing";

const CONTEXT_DISPLAY_LABELS: Record<string, string> = {
  beauty_nail: "\ub124\uc77c",
  beauty_salon: "\ubdf0\ud2f0/\ubbf8\uc6a9",
  brand_awareness: "\ube0c\ub79c\ub4dc \uc778\uc9c0\ub3c4",
  cafe: "\uce74\ud398",
  discount_event: "\ud560\uc778 \uc774\ubca4\ud2b8",
  new_launch: "\uc2e0\uba54\ub274/\uc2e0\uc0c1\ud488 \ucd9c\uc2dc",
  reservation_cta: "\uc608\uc57d/\ubc29\ubb38 \uc720\ub3c4",
  restaurant: "\uc74c\uc2dd\uc810/\uc2dd\ub2f9",
  retention: "\uc7ac\ubc29\ubb38 \uc720\ub3c4",
  review_event: "\ub9ac\ubdf0 \uc774\ubca4\ud2b8",
  seasonal_limited: "\uc2dc\uc98c \ud55c\uc815 \ud64d\ubcf4",
  store: "\uc77c\ubc18 \ub9e4\uc7a5/\uc18c\ub9e4",
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
