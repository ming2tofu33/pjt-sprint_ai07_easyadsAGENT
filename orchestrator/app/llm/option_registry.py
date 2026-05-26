"""Option question registry for LLM/LangGraph human-in-the-loop prompts."""

from __future__ import annotations

from orchestrator.app.schemas.llm_marketing import MissingField, OptionItem, OptionQuestion


OPTION_FIELD_PRIORITY: dict[str, int] = {
    "business_type": 0,
    "item_or_service": 0,
    "promotion_goal": 0,
    "ad_format": 0,
    "target_persona": 1,
    "region_type": 1,
    "brand_tone": 1,
    "usp": 2,
    "time_context": 2,
    "price_or_discount": 2,
    "brand_name": 2,
    "contact_or_order_method": 2,
    "custom_request": 3,
}


# platform/aspect_ratio/location_text are inferred by FormatPlanner or free-text parsing,
# not asked through the default OptionQuestionRegistry in MVP.
OPTION_QUESTION_REGISTRY: dict[MissingField, OptionQuestion] = {
    "business_type": OptionQuestion(
        field="business_type",
        question="어떤 업종의 광고인가요?",
        options=[
            OptionItem(id=1, label="음식점/식당", value="restaurant"),
            OptionItem(id=2, label="카페/디저트", value="cafe"),
            OptionItem(id=3, label="뷰티/미용실", value="beauty_salon"),
            OptionItem(id=4, label="주점/바", value="bar"),
            OptionItem(id=5, label="피트니스/헬스", value="fitness"),
            OptionItem(id=6, label="학원/교육", value="academy"),
            OptionItem(id=7, label="꽃집", value="flower_shop"),
            OptionItem(id=8, label="일반 매장/소매", value="store"),
            OptionItem(id=9, label="직접 입력", value="custom"),
        ],
    ),
    "item_or_service": OptionQuestion(
        field="item_or_service",
        question="홍보할 상품이나 서비스는 무엇인가요?",
        options=[
            OptionItem(id=1, label="대표 메뉴", value="signature_item"),
            OptionItem(id=2, label="신상품", value="new_item"),
            OptionItem(id=3, label="패키지/세트", value="bundle"),
            OptionItem(id=4, label="예약 서비스", value="reservation_service"),
            OptionItem(id=5, label="직접 입력", value="custom"),
        ],
    ),
    "promotion_goal": OptionQuestion(
        field="promotion_goal",
        question="어떤 목적의 광고를 만들까요?",
        options=[
            OptionItem(id=1, label="신메뉴/신상품 출시", value="new_launch"),
            OptionItem(id=2, label="시즌 한정 홍보", value="seasonal_limited"),
            OptionItem(id=3, label="할인 이벤트", value="discount_event"),
            OptionItem(id=4, label="예약/방문 유도", value="reservation_cta"),
            OptionItem(id=5, label="브랜드 인지도", value="brand_awareness"),
            OptionItem(id=6, label="리뷰 이벤트", value="review_event"),
            OptionItem(id=7, label="재방문 유도", value="retention"),
            OptionItem(id=8, label="직접 입력", value="custom"),
        ],
    ),
    "ad_format": OptionQuestion(
        field="ad_format",
        question="어디에 사용할 광고인가요?",
        options=[
            OptionItem(id=1, label="인스타그램 피드 1:1", value="instagram_feed"),
            OptionItem(id=2, label="인스타그램 스토리 9:16", value="instagram_story"),
            OptionItem(id=3, label="포스터 4:5", value="poster"),
            OptionItem(id=4, label="전단지 A4", value="flyer"),
            OptionItem(id=5, label="웹 배너 16:9", value="banner"),
            OptionItem(id=6, label="상품 상세 페이지", value="product_detail"),
            OptionItem(id=7, label="기타 사이즈", value="custom"),
        ],
    ),
    "target_persona": OptionQuestion(
        field="target_persona",
        question="주요 고객층을 선택해주세요.",
        options=[
            OptionItem(id=1, label="20대 대학생", value="college_student"),
            OptionItem(id=2, label="30~40대 직장인", value="office_worker"),
            OptionItem(id=3, label="20~30대 커플/친구", value="young_social"),
            OptionItem(id=4, label="관광객", value="tourist"),
            OptionItem(id=5, label="가족/동네 단골", value="family_local"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "region_type": OptionQuestion(
        field="region_type",
        question="매장이 위치한 상권 유형은 어디에 가깝나요?",
        options=[
            OptionItem(id=1, label="오피스 상권", value="office_district"),
            OptionItem(id=2, label="대학가", value="university_area"),
            OptionItem(id=3, label="핫플/번화가", value="trendy_district"),
            OptionItem(id=4, label="관광지", value="tourist_spot"),
            OptionItem(id=5, label="주거 지역", value="residential_area"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "brand_tone": OptionQuestion(
        field="brand_tone",
        question="광고 분위기는 어떤 톤이 좋나요?",
        options=[
            OptionItem(id=1, label="따뜻하고 편안한", value="warm_cozy"),
            OptionItem(id=2, label="힙하고 트렌디한", value="hip_trendy"),
            OptionItem(id=3, label="고급스러운", value="premium_luxurious"),
            OptionItem(id=4, label="깔끔한", value="clean_minimal"),
            OptionItem(id=5, label="강렬하고 긴급한", value="bold_urgent"),
            OptionItem(id=6, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "usp": OptionQuestion(
        field="usp",
        question="꼭 강조하고 싶은 장점이 있나요?",
        options=[
            OptionItem(id=1, label="가성비", value="value_for_money"),
            OptionItem(id=2, label="프리미엄 품질", value="premium_quality"),
            OptionItem(id=3, label="신선함", value="freshness"),
            OptionItem(id=4, label="빠른 예약/주문", value="easy_order"),
            OptionItem(id=5, label="직접 입력", value="custom"),
        ],
        required=False,
        multi_select=True,
    ),
    "time_context": OptionQuestion(
        field="time_context",
        question="언제 사용할 광고인가요?",
        options=[
            OptionItem(id=1, label="점심", value="lunch"),
            OptionItem(id=2, label="저녁", value="dinner"),
            OptionItem(id=3, label="주말", value="weekend"),
            OptionItem(id=4, label="시즌/기념일", value="seasonal"),
            OptionItem(id=5, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "price_or_discount": OptionQuestion(
        field="price_or_discount",
        question="가격이나 할인 정보를 넣을까요?",
        options=[
            OptionItem(id=1, label="가격 강조", value="price_focus"),
            OptionItem(id=2, label="할인율 강조", value="discount_focus"),
            OptionItem(id=3, label="혜택만 강조", value="benefit_focus"),
            OptionItem(id=4, label="넣지 않음", value="none"),
            OptionItem(id=5, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "brand_name": OptionQuestion(
        field="brand_name",
        question="브랜드명이나 매장명을 넣을까요?",
        options=[
            OptionItem(id=1, label="넣기", value="include"),
            OptionItem(id=2, label="넣지 않기", value="none"),
            OptionItem(id=3, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "contact_or_order_method": OptionQuestion(
        field="contact_or_order_method",
        question="예약/주문 방법을 넣을까요?",
        options=[
            OptionItem(id=1, label="전화", value="phone"),
            OptionItem(id=2, label="DM", value="dm"),
            OptionItem(id=3, label="네이버 예약", value="naver_booking"),
            OptionItem(id=4, label="매장 방문", value="visit"),
            OptionItem(id=5, label="직접 입력", value="custom"),
        ],
        required=False,
    ),
    "custom_request": OptionQuestion(
        field="custom_request",
        question="추가로 반영할 요청이 있나요?",
        options=[
            OptionItem(id=1, label="있음", value="include_custom_request"),
            OptionItem(id=2, label="없음", value="none"),
        ],
        required=False,
    ),
}


def get_option_question(field: MissingField) -> OptionQuestion:
    return OPTION_QUESTION_REGISTRY[field]


def get_next_missing_field(missing_fields: list[MissingField]) -> MissingField | None:
    registered = [field for field in missing_fields if field in OPTION_QUESTION_REGISTRY]
    if not registered:
        return None
    return min(registered, key=lambda field: OPTION_FIELD_PRIORITY.get(field, 99))




