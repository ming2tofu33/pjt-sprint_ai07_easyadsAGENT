"""Deterministic copy fallback library for Copy Quality Core v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orchestrator.app.llm.option_registry import option_label_for_value
from orchestrator.app.schemas.llm_marketing import CopyCandidate, CopyMessageStrategy


ANGLES = ("product_first", "emotion_first", "benefit_action_first")


@dataclass(frozen=True)
class CopyTheme:
    key: str
    aliases: tuple[str, ...]
    ctas: tuple[str, str, str]
    product_headline: str
    emotion_headline: str
    action_headline: str
    product_subcopy: str
    emotion_subcopy: str
    action_subcopy: str
    voice: str


THEMES: tuple[CopyTheme, ...] = (
    CopyTheme("cafe", ("cafe", "dessert", "bakery"), ("신메뉴 보기", "오늘 만나보기", "메뉴 확인하기"), "{item} 신메뉴", "오늘의 달콤한 한 잔", "{item}, 지금 만나보기", "부드럽고 산뜻한 카페 혜택 메뉴", "잠깐의 휴식에 어울리는 달콤함", "오늘 혜택과 함께 즐기기 좋은 메뉴", "warm seasonal cafe copy"),
    CopyTheme("restaurant_bbq", ("restaurant", "restaurant_bbq", "bbq", "meat_restaurant", "korean_food"), ("예약 문의하기", "지금 예약하기", "회식 문의하기"), "숯불향 가득한 한상", "회식은 역시 {item}", "{item} 예약 가능", "따뜻하게 구워 즐기는 프리미엄 메뉴", "모임과 회식에 어울리는 든든한 시간", "편한 저녁 자리를 미리 준비하세요", "appetizing reservation copy"),
    CopyTheme("beauty_skincare", ("beauty", "beauty_skincare", "skincare", "salon"), ("상담 예약하기", "케어 문의하기", "예약 문의하기"), "맑은 피부 루틴", "깨끗하게 빛나는 시간", "맞춤 케어 상담", "나에게 맞춘 프리미엄 스킨케어", "차분하고 깨끗한 케어 경험", "피부 고민에 맞춰 상담해보세요", "clean trustworthy beauty copy"),
    CopyTheme("beauty_hair", ("beauty_hair", "hair", "hair_salon"), ("예약 상담하기", "스타일 상담하기", "헤어 상담하기"), "오늘의 스타일 변화", "나에게 어울리는 무드", "헤어 상담 예약", "얼굴형과 취향에 맞춘 헤어 제안", "기분까지 달라지는 스타일링", "원하는 스타일을 상담으로 시작하세요", "stylish salon copy"),
    CopyTheme("beauty_nail", ("beauty_nail", "nail"), ("디자인 상담하기", "예약 문의하기", "무드 상담하기"), "감각적인 네일 디자인", "손끝에 남는 무드", "네일 디자인 상담", "계절과 취향을 담은 섬세한 디자인", "작은 디테일까지 기분 좋게", "원하는 무드를 상담해보세요", "delicate nail copy"),
    CopyTheme("beauty_spa", ("beauty_spa", "spa", "wellness"), ("예약 문의하기", "케어 예약하기", "상담 예약하기"), "부드러운 웰니스 케어", "하루를 쉬게 하는 시간", "스파 예약 문의", "몸과 마음을 차분하게 쉬게 하는 케어", "조용히 회복되는 프리미엄 휴식", "원하는 시간에 맞춰 문의하세요", "calm wellness copy"),
    CopyTheme("fitness", ("fitness", "gym", "pilates", "yoga"), ("상담 예약하기", "프로그램 보기", "체험 문의하기"), "나에게 맞는 운동 루틴", "가볍게 시작하는 변화", "오늘부터 루틴 시작", "목표와 생활에 맞춘 운동 프로그램", "무리 없이 이어가는 건강한 습관", "상담으로 내 루틴을 찾아보세요", "supportive fitness copy"),
    CopyTheme("clinic", ("clinic", "dental", "medical"), ("상담 예약하기", "진료 문의하기", "예약 문의하기"), "꼼꼼한 상담과 진료", "안심하고 묻는 시간", "진료 상담 예약", "필요한 내용을 차분하게 확인합니다", "편안하게 상담받을 수 있는 안내", "방문 전 상담으로 확인해보세요", "careful clinic copy"),
    CopyTheme("education", ("education", "academy", "class", "tutoring"), ("상담 신청하기", "수업 문의하기", "커리큘럼 보기"), "맞춤 학습 커리큘럼", "배움이 달라지는 순간", "학습 상담 신청", "목표와 수준에 맞춰 설계한 수업", "꾸준히 성장하는 학습 경험", "상담으로 필요한 수업을 확인하세요", "clear education copy"),
    CopyTheme("retail", ("retail", "shop", "fashion", "store"), ("상품 보기", "컬렉션 보기", "문의하기"), "{item} 컬렉션", "오늘의 취향을 고르는 시간", "{item} 지금 보기", "취향과 일상에 어울리는 셀렉션", "작은 선택으로 분위기를 바꿔보세요", "준비된 상품을 지금 확인하세요", "curated retail copy"),
    CopyTheme("generic", ("generic", "store", "service"), ("문의하기", "예약하기", "자세히 보기"), "{item} 안내", "필요한 순간에 맞춘 선택", "{item} 문의하기", "핵심 정보를 간결하게 전하는 안내", "고객에게 필요한 가치를 분명하게 전합니다", "궁금한 내용을 편하게 문의하세요", "clear generic copy"),
)


def build_message_strategy(context: Any) -> CopyMessageStrategy:
    item = _display_item(_get(context, "item_or_service"))
    promotion_goal = _get(context, "promotion_goal")
    target = _get(context, "target_persona")
    brand_voice = _get(context, "brand_tone")
    theme = resolve_copy_theme(_get(context, "business_type"))
    return CopyMessageStrategy(
        target_persona=target,
        product_truths=[str(item)],
        customer_desires=[_goal_to_desire(promotion_goal)],
        promotion_intent=promotion_goal,
        brand_voice=brand_voice or theme.voice,
        message_angles=list(ANGLES),
        forbidden_claims=["invented price", "invented discount", "invented phone", "guaranteed effect"],
        strategy_summary=f"{theme.key}: {item} 중심의 3-angle 광고 카피",
        metadata={"theme": theme.key},
    )


def generate_fallback_candidates(context: Any, max_candidates: int = 3) -> list[CopyCandidate]:
    item = _display_item(_get(context, "item_or_service"))
    theme = resolve_copy_theme(_get(context, "business_type"))
    strategy = build_message_strategy(context)
    product_headline = theme.product_headline
    product_subcopy = theme.product_subcopy
    emotion_headline = theme.emotion_headline
    emotion_subcopy = theme.emotion_subcopy
    if theme.key == "restaurant_bbq" and item == "예약 서비스":
        product_headline = "{item} 안내"
        product_subcopy = "방문 전 필요한 내용을 편하게 확인하세요"
        emotion_headline = "오늘 일정, 미리 잡아두세요"
        emotion_subcopy = "기다림을 줄이고 편하게 방문하세요"
    templates = (
        ("product_first", product_headline, product_subcopy, theme.ctas[0], "product"),
        ("emotion_first", emotion_headline, emotion_subcopy, theme.ctas[1], "emotion"),
        ("benefit_action_first", theme.action_headline, theme.action_subcopy, theme.ctas[2], "action"),
    )
    candidates: list[CopyCandidate] = []
    for index, (angle, headline, subcopy, cta, tone) in enumerate(templates[: max(1, max_candidates)], start=1):
        candidates.append(
            CopyCandidate(
                id=f"copy_{index}",
                headline=headline.format(item=item),
                subcopy=subcopy.format(item=item),
                cta=cta,
                tone_label=tone,
                angle=angle,  # type: ignore[arg-type]
                strategy_summary=strategy.strategy_summary,
                rationale=f"{angle} deterministic fallback for {theme.key}.",
                metadata={"copy_quality_v2": True, "theme": theme.key},
            )
        )
    return candidates


def resolve_copy_theme(business_type: str | None) -> CopyTheme:
    key = (business_type or "generic").strip().lower()
    for theme in THEMES:
        if key == theme.key or key in theme.aliases:
            return theme
    return THEMES[-1]


def _goal_to_desire(goal: str | None) -> str:
    if goal == "reservation_cta":
        return "방문 전 편하게 예약하고 싶음"
    if goal == "new_launch":
        return "새로운 메뉴나 상품을 먼저 알고 싶음"
    if goal == "discount_event":
        return "부담 없이 혜택을 확인하고 싶음"
    if goal == "review_event":
        return "경험을 공유하고 참여하고 싶음"
    return "필요한 정보를 빠르게 확인하고 싶음"


def _display_item(value: str | None) -> str:
    if not value:
        return "상품"
    label = option_label_for_value("item_or_service", value)
    if label:
        return label
    if "_" in value and value.isascii():
        return "상품"
    return value


def _get(context: Any, key: str) -> Any:
    if isinstance(context, dict):
        return context.get(key)
    return getattr(context, key, None)
