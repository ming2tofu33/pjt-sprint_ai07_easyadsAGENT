"""Deterministic copy fallback library for Copy Quality Core v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orchestrator.app.llm.copy_subject_anchor import resolve_copy_subject_anchor
from orchestrator.app.llm.copy_tone_policy import resolve_copy_route_key
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
    CopyTheme("restaurant_bbq", (), ("예약 문의하기", "지금 예약하기", "회식 문의하기"), "숯불향 가득한 한상", "회식은 역시 {item}", "{item} 예약 가능", "따뜻하게 구워 즐기는 프리미엄 메뉴", "모임과 회식에 어울리는 든든한 시간", "편한 저녁 자리를 미리 준비하세요", "appetizing reservation copy"),
    CopyTheme("beauty_skincare", ("beauty_skincare", "skincare"), ("상담 예약하기", "케어 문의하기", "예약 문의하기"), "맑은 피부 루틴", "깨끗하게 빛나는 시간", "맞춤 케어 상담", "차분한 프리미엄 스킨케어", "깨끗한 무드를 위한 케어 경험", "피부 컨디션을 상담해보세요", "clean trustworthy beauty copy"),
    CopyTheme("beauty_hair", ("beauty_hair", "hair", "hair_salon"), ("예약 상담하기", "스타일 상담하기", "헤어 상담하기"), "오늘의 스타일 변화", "나에게 어울리는 무드", "헤어 상담 예약", "새로운 분위기를 위한 헤어 제안", "기분까지 달라지는 스타일링", "원하는 스타일을 상담으로 시작하세요", "stylish salon copy"),
    CopyTheme("beauty_nail", ("beauty_nail", "nail"), ("디자인 상담하기", "예약 문의하기", "무드 상담하기"), "감각적인 네일 디자인", "손끝에 남는 무드", "네일 디자인 상담", "계절과 취향을 담은 섬세한 디자인", "작은 디테일까지 기분 좋게", "원하는 무드를 상담해보세요", "delicate nail copy"),
    CopyTheme("beauty_spa", ("beauty_spa", "spa", "wellness"), ("예약 문의하기", "케어 예약하기", "상담 예약하기"), "부드러운 웰니스 케어", "하루를 쉬게 하는 시간", "스파 예약 문의", "몸과 마음을 차분하게 쉬게 하는 케어", "조용히 회복되는 프리미엄 휴식", "원하는 시간에 맞춰 문의하세요", "calm wellness copy"),
    CopyTheme("fitness", ("fitness", "gym", "pilates", "yoga"), ("상담 예약하기", "프로그램 보기", "체험 문의하기"), "가볍게 시작하는 운동 루틴", "가볍게 시작하는 변화", "오늘부터 루틴 시작", "꾸준히 이어가기 좋은 운동 프로그램", "무리 없이 이어가는 건강한 습관", "운동 상담으로 루틴을 시작하세요", "supportive fitness copy"),
    CopyTheme("clinic", ("clinic", "dental", "medical"), ("상담 예약하기", "진료 문의하기", "예약 문의하기"), "꼼꼼한 상담과 진료", "안심하고 묻는 시간", "진료 상담 예약", "필요한 내용을 차분하게 확인합니다", "편안하게 상담받을 수 있는 안내", "방문 전 상담으로 확인해보세요", "careful clinic copy"),
    CopyTheme("education", ("education", "academy", "class", "tutoring"), ("상담 신청하기", "수업 문의하기", "커리큘럼 보기"), "배움의 다음 단계를 위한 수업", "배움이 달라지는 순간", "학습 상담 신청", "차분히 이어가는 학습 루틴", "꾸준히 성장하는 학습 경험", "상담으로 수업 방향을 정해보세요", "clear education copy"),
    CopyTheme("retail", ("retail", "shop", "fashion", "store"), ("상품 보기", "컬렉션 보기", "문의하기"), "{item} 컬렉션", "오늘의 취향을 고르는 시간", "{item} 둘러보기", "취향과 일상에 어울리는 셀렉션", "작은 선택으로 분위기를 바꿔보세요", "새로운 컬렉션을 둘러보세요", "curated retail copy"),
    CopyTheme("macaron", ("macaron", "dessert_macaron"), ("라인업 보기", "오늘 만나보기", "예약 문의하기"), "마카롱 컬렉션", "달콤한 색을 고르는 시간", "마카롱 예약 문의", "선물하기 좋은 디저트 라인업", "작은 디저트가 주는 기분 좋은 순간", "원하는 구성은 매장에 문의하세요", "delicate dessert copy"),
    CopyTheme("photo_studio", ("photo_studio", "flower_profile", "profile_photo"), ("예약 문의하기", "촬영 상담하기", "일정 문의하기"), "꽃다발 프로필 촬영", "오늘을 오래 남기는 장면", "촬영 일정 상담", "인물과 분위기를 담는 프로필 촬영", "소중한 순간을 자연스럽게 남겨보세요", "원하는 무드를 상담해보세요", "warm photography copy"),
    CopyTheme("car_detailing", ("car_detailing", "car_care", "vehicle_detailing"), ("예약 문의하기", "관리 상담하기", "서비스 문의하기"), "차량 디테일링 관리", "깨끗함이 오래 남는 시간", "차량 관리 상담", "실내외 컨디션을 정돈하는 관리", "매일 타는 차를 더 산뜻하게", "차량 상태에 맞춰 상담해보세요", "clean vehicle care copy"),
    CopyTheme("generic", ("generic", "store", "service"), ("문의하기", "예약하기", "상담하기"), "{item} 상담 안내", "필요한 순간에 맞춘 선택", "{item} 문의하기", "상황에 맞춰 안내받는 상담", "고객의 상황에 맞춰 차분히 안내합니다", "궁금한 내용을 편하게 문의하세요", "clear generic copy"),
)


def build_message_strategy(context: Any) -> CopyMessageStrategy:
    item = _display_item(_anchor_value(context))
    promotion_goal = _get(context, "promotion_goal")
    target = _get(context, "target_persona")
    brand_voice = _get(context, "brand_tone")
    theme = resolve_copy_theme(_get(context, "business_type"))
    desire = _goal_to_desire(promotion_goal)
    conversion_goal = _conversion_goal(promotion_goal)
    cta_intent = _cta_intent(promotion_goal)
    proof_or_detail = _proof_or_detail(theme.key)
    if promotion_goal == "menu_discovery":
        conversion_goal = "menu_discovery"
        cta_intent = "explore_menu"
        desire = "메뉴와 맛 구성을 가볍게 둘러보고 싶음"
        if theme.key == "macaron":
            proof_or_detail = "다양한 맛과 색의 마카롱 컬렉션"
    return CopyMessageStrategy(
        target_persona=target,
        product_truths=[str(item)],
        customer_desires=[desire],
        promotion_intent=promotion_goal,
        brand_voice=brand_voice or theme.voice,
        primary_value=item,
        customer_desire=desire,
        emotional_hook=_emotional_hook(theme.key),
        proof_or_detail=proof_or_detail,
        conversion_goal=conversion_goal,
        headline_angle="product/emotion/action",
        cta_intent=cta_intent,
        supported_facts=[str(item)],
        message_angles=list(ANGLES),
        forbidden_claims=["invented price", "invented discount", "invented phone", "guaranteed effect"],
        strategy_summary=f"{theme.key}: {item} 중심의 3-angle 광고 카피",
        metadata={"theme": theme.key},
    )


def generate_fallback_candidates(context: Any, max_candidates: int = 3) -> list[CopyCandidate]:
    item = _display_item(_anchor_value(context))
    theme = resolve_copy_theme(_get(context, "business_type"))
    strategy = build_message_strategy(context)
    product_headline = theme.product_headline
    product_subcopy = theme.product_subcopy
    emotion_headline = theme.emotion_headline
    emotion_subcopy = theme.emotion_subcopy
    ctas = theme.ctas
    if theme.key == "macaron" and _get(context, "promotion_goal") == "menu_discovery":
        ctas = ("컬렉션 보기", "오늘의 맛 보기", "")
    if theme.key == "restaurant_bbq" and item == "예약 서비스":
        product_headline = "{item} 안내"
        product_subcopy = "방문 전 필요한 내용을 편하게 확인하세요"
        emotion_headline = "오늘 일정, 미리 잡아두세요"
        emotion_subcopy = "기다림을 줄이고 편하게 방문하세요"
    templates = (
        ("product_first", product_headline, product_subcopy, ctas[0], "product"),
        ("emotion_first", emotion_headline, emotion_subcopy, ctas[1], "emotion"),
        ("benefit_action_first", theme.action_headline, theme.action_subcopy, ctas[2], "action"),
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
    key = resolve_copy_route_key(business_type)
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
    if goal == "consultation":
        return "상담으로 다음 단계를 정하고 싶음"
    if goal == "menu_discovery":
        return "메뉴 구성을 편하게 살펴보고 싶음"
    if goal == "visit":
        return "방문 전에 분위기를 알고 싶음"
    if goal == "inquiry":
        return "궁금한 내용을 문의하고 싶음"
    if goal == "purchase":
        return "구매 전에 상품을 살펴보고 싶음"
    return "상담이나 문의로 필요한 내용을 확인하고 싶음"


def _conversion_goal(goal: str | None) -> str:
    if goal == "reservation_cta":
        return "reservation"
    if goal == "purchase":
        return "purchase"
    if goal in {"consultation", "inquiry"}:
        return "consultation"
    return "visit_or_interest"


def _cta_intent(goal: str | None) -> str:
    if goal == "reservation_cta":
        return "예약 문의"
    if goal == "consultation":
        return "상담 신청"
    if goal == "new_launch":
        return "신규 상품 탐색"
    return "문의 또는 방문 유도"


def _emotional_hook(theme: str) -> str:
    return {
        "cafe": "잠깐의 휴식",
        "restaurant_bbq": "따뜻한 모임",
        "beauty_skincare": "차분한 케어",
        "beauty_hair": "새로운 분위기",
        "beauty_nail": "손끝의 무드",
    }.get(theme, "필요한 순간에 맞춘 선택")


def _proof_or_detail(theme: str) -> str:
    return {
        "cafe": "디저트와 음료",
        "restaurant_bbq": "예약과 방문",
        "beauty_skincare": "상담 기반 케어",
        "car_detailing": "차량 상태 상담",
    }.get(theme, "상담 가능한 서비스")


def _display_item(value: str | None) -> str:
    if not value:
        return "상품"
    label = option_label_for_value("item_or_service", value)
    if label:
        return label
    if "_" in value and value.isascii():
        return "상품"
    return value


def _anchor_value(context: Any) -> str | None:
    return resolve_copy_subject_anchor(context).value


def _get(context: Any, key: str) -> Any:
    if isinstance(context, dict):
        if key in context:
            return context.get(key)
        nested = context.get("context")
        if isinstance(nested, dict):
            return nested.get(key)
        return getattr(nested, key, None) if nested is not None else None
    return getattr(context, key, None)
