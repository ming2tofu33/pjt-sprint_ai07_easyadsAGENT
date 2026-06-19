# Business Domain Routing 공용 계약 v1

## 1. 합의된 핵심 원칙

이번 계약은 다음 문제를 방지하는 것을 목적으로 한다.

```
- business_type에 업종·상품·씬·스타일이 혼합되는 문제
- 신규 업종 추가 시 여러 파일을 동시에 수정해야 하는 문제
- 미지원 업종이 이유 없이 generic으로 증발하는 문제
- restaurant_bbq처럼 업종과 장면이 하나의 값으로 결합되는 문제
- beauty_salon이 근거 없이 skincare 또는 hair로 변환되는 문제
- preset과 template이 서로 다른 업종을 선택하는 문제
```

최종 원칙은 다음과 같다.

```
1. Canonical business domain은 상위 업종만 표현한다.
2. 상품, 서비스 세부 유형, 조리법, 장면, 분위기는 tag 축으로 분리한다.
3. Canonical 결과에는 레거시 preset/template key를 넣지 않는다.
4. 레거시 key는 전환 기간의 compatibility adapter에서만 생성한다.
5. 미지원 업종과 모호한 입력은 조용히 generic으로 보내지 않는다.
6. 모든 fallback에는 이유와 근거가 남아야 한다.
```

---

# 2. 팀 결정사항 최종안

## 결정 1. MVP 공식 Canonical Domain

1차 MVP에서 공식 지원하는 canonical domain은 다음 세 개다.

```
food_and_beverage
beauty
retail
```

그 외 입력을 보존하기 위한 값으로 `other`를 둔다.

```python
class CanonicalBusinessDomain(StrEnum):
    FOOD_AND_BEVERAGE = "food_and_beverage"
    BEAUTY = "beauty"
    RETAIL = "retail"
    OTHER = "other"
```

### F&B에 포함되는 사례

```
cafe
restaurant
bakery
dessert shop
bar
food delivery brand
meal kit brand
```

단, `cafe`, `restaurant`, `bakery`는 canonical domain이 아니라 `business_tags` 또는 `venue_type`으로 표현한다.

### Beauty에 포함되는 사례

```
skincare
cosmetics
hair salon
nail salon
eyebrow service
spa
beauty clinic
```

세부 유형은 `business_tags`로 표현한다.

### Retail에 포함되는 사례

```
physical store
online shop
fashion retail
home goods store
electronics shop
general ecommerce
```

### MVP 비공식 도메인

```
fitness
education
professional service
local service
hospitality
technology
home service
```

이 값들은 현재 공식 specialized domain으로 선언하지 않는다.

대신 다음처럼 처리한다.

```
canonical_domain = other
support_status = generic_fallback
unsupported_domain_hint = 원래 인식된 업종
fallback_reason = unsupported_domain_in_mvp
```

원래 입력을 버리면 안 된다.

---

## 결정 2. `restaurant_bbq` 분리

`restaurant_bbq`는 canonical business domain으로 사용하지 않는다.

다음처럼 분리한다.

```
canonical_domain:
food_and_beverage

business_tags:
restaurant
korean_bbq

scene_tags:
bbq_grill
charcoal_grill
table_grill
```

`bbq_grill` scene은 다음 중 하나 이상의 근거가 있을 때만 활성화한다.

```
- 사용자가 숯불, 불판, 구이, 바비큐를 명시함
- 상품 자체가 grilled meat로 확인됨
- 이미지에서 grill 또는 charcoal이 명확히 관찰됨
- reference가 명시적으로 grill scene을 요구함
```

다음만으로는 활성화하면 안 된다.

```
사업장이 고깃집이다
restaurant 태그가 있다
business_type이 과거 restaurant_bbq였다
```

예:

```
고깃집 + 감자튀김
→ food_and_beverage
→ business_tags=["restaurant", "korean_bbq"]
→ scene_tags에 bbq_grill 없음
→ 불판·숯불 생성 금지

고깃집 + 숯불 삼겹살
→ food_and_beverage
→ business_tags=["restaurant", "korean_bbq"]
→ scene_tags=["bbq_grill", "charcoal_grill"]
→ 불판·숯불 허용
```

---

## 결정 3. `beauty_salon` 처리

`beauty_salon`은 skincare로 자동 변환하지 않는다.

Canonical 결과:

```
canonical_domain = beauty
```

세부 route를 결정하려면 다음 evidence가 필요하다.

```
skincare
cosmetics
hair
nail
eyebrow
spa
massage
aesthetic clinic
```

예:

```
"네일샵 광고"
→ business_tags=["beauty_service", "nail"]

"세럼을 홍보하고 싶어"
→ business_tags=["beauty_product", "skincare"]

"눈썹 시술 홍보"
→ business_tags=["beauty_service", "eyebrow"]
```

입력이 단순히 다음과 같다면:

```
"뷰티살롱을 홍보하고 싶어"
```

결과:

```
canonical_domain = beauty
support_status = needs_evidence
clarification_required = true
fallback_reason = ambiguous_beauty_subdomain
```

추가 evidence가 없는 상태에서는 다음으로 보내면 안 된다.

```
beauty_skincare
beauty_hair
beauty_nail
beauty_spa
```

전환 기간의 레거시 경로에서는 중립적인 `generic` route를 사용하되, breadcrumb를 남긴다.

향후 neutral beauty preset이 추가되면:

```
beauty_generic
```

으로 교체할 수 있다.

---

## 결정 4. 미지원 업종 처리

다음은 MVP specialized domain으로 보지 않는다.

```
fitness
education
service
professional service
hospitality
technology
```

처리 방식:

```
canonical_domain = other
support_status = generic_fallback
fallback_reason = unsupported_domain_in_mvp
unsupported_domain_hint = 인식된 원래 업종
```

예:

```python
DomainRoutingResult(
    raw_business_type="헬스장",
    canonical_domain=CanonicalBusinessDomain.OTHER,
    support_status=DomainSupportStatus.GENERIC_FALLBACK,
    unsupported_domain_hint="fitness",
    fallback_reason=DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP,
    business_tags=[
        RoutingTagEvidence(
            tag="fitness",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.98,
        ),
    ],
    scene_tags=[],
    style_tags=[],
    matched_aliases=["헬스장"],
    clarification_required=False,
    unresolved_questions=[],
    confidence=0.98,
)
```

`retail`은 MVP 공식 domain이므로 generic 위임 대상에서 제외한다.

---

## 결정 5. Reference Template Metadata

Reference template에는 business domain과 scene/style 정보를 모두 저장한다.

단, 기존처럼 `business_types` 한 필드에 모두 섞어 넣으면 안 된다.

다음처럼 별도 축으로 저장한다.

```
business_domains
business_tags
product_tags
scene_tags
style_tags
placements
```

이유:

```
- 고객은 같은 업종뿐 아니라 비슷한 분위기와 구도를 선택함
- 업종과 스타일을 한 배열에 섞으면 라우팅 의미가 다시 붕괴함
- business match와 style match의 가중치를 별도로 계산해야 함
- 같은 레퍼런스가 여러 업종에 스타일 참고용으로 사용될 수 있음
```

예:

```python
ReferenceTemplateRoutingProfile(
    business_domains={
        CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    },
    business_tags={
        "cafe",
        "dessert_shop",
    },
    product_tags={
        "dessert",
        "beverage",
    },
    scene_tags={
        "tabletop",
        "product_closeup",
        "negative_space_top",
    },
    style_tags={
        "soft_pastel",
        "editorial",
        "minimal",
    },
    placements={
        "instagram_feed",
        "instagram_story",
    },
)
```

---

# 3. 최종 공용 타입 계약

## 3.1 Canonical Domain

```python
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

class CanonicalBusinessDomain(StrEnum):
    FOOD_AND_BEVERAGE = "food_and_beverage"
    BEAUTY = "beauty"
    RETAIL = "retail"
    OTHER = "other"
```

`cafe`, `restaurant`, `restaurant_bbq`, `beauty_skincare`, `fitness` 등을 이 enum에 추가하지 않는다.

---

## 3.2 Support Status

```python
class DomainSupportStatus(StrEnum):
    SPECIALIZED = "specialized"
    GENERIC_FALLBACK = "generic_fallback"
    NEEDS_EVIDENCE = "needs_evidence"
    UNRESOLVED = "unresolved"
```

의미:

```
specialized:
공식 domain이며 route에 필요한 근거가 충분함

generic_fallback:
업종은 이해했지만 MVP specialized 전략이 없음

needs_evidence:
상위 domain은 알지만 세부 route를 결정할 evidence가 부족함

unresolved:
업종 자체를 신뢰할 수준으로 해석하지 못함
```

---

## 3.3 Fallback Reason

```python
class DomainFallbackReason(StrEnum):
    UNSUPPORTED_DOMAIN_IN_MVP = "unsupported_domain_in_mvp"
    AMBIGUOUS_BEAUTY_SUBDOMAIN = "ambiguous_beauty_subdomain"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_SPECIALIZED_VISUAL_PROFILE = "no_specialized_visual_profile"
    UNRECOGNIZED_BUSINESS_TYPE = "unrecognized_business_type"
```

자유 문자열로 두지 않는다.

운영 집계가 가능해야 하기 때문이다.

---

## 3.4 Evidence Source

```python
class RoutingEvidenceSource(StrEnum):
    USER_TEXT = "user_text"
    IMAGE_VLM = "image_vlm"
    BRIEF_LLM = "brief_llm"
    ASSET_METADATA = "asset_metadata"
    BRAND_PROFILE = "brand_profile"
    REFERENCE_METADATA = "reference_metadata"
    LEGACY_ALIAS = "legacy_alias"
```

---

## 3.5 Routing Tag Evidence

```python
class RoutingTagEvidence(BaseModel):
    tag: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )

    source: RoutingEvidenceSource
    confidence: float = Field(ge=0.0, le=1.0)

    usable_for_routing: bool = True
    evidence_ref: str | None = None
```

태그는 open vocabulary로 유지한다.

예:

```
restaurant
cafe
korean_bbq
hair
nail
eyebrow
skincare
ecommerce
physical_store
bbq_grill
product_closeup
editorial
premium
```

새 상품이나 서비스가 들어와도 enum을 수정하지 않는다.

---

## 3.6 Canonical Domain Routing Result

```python
class DomainRoutingResult(BaseModel):
    contract_version: Literal["1.0"] = "1.0"

    raw_business_type: str | None

    canonical_domain: CanonicalBusinessDomain
    support_status: DomainSupportStatus

    unsupported_domain_hint: str | None = None

    business_tags: list[RoutingTagEvidence] = Field(
        default_factory=list,
    )
    scene_tags: list[RoutingTagEvidence] = Field(
        default_factory=list,
    )
    style_tags: list[RoutingTagEvidence] = Field(
        default_factory=list,
    )

    fallback_reason: DomainFallbackReason | None = None

    matched_aliases: list[str] = Field(
        default_factory=list,
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
    )

    clarification_required: bool = False
    unresolved_questions: list[str] = Field(
        default_factory=list,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @model_validator(mode="after")
    def validate_status_contract(self) -> "DomainRoutingResult":
        if self.support_status == DomainSupportStatus.SPECIALIZED:
            if self.fallback_reason is not None:
                raise ValueError(
                    "specialized routing must not include fallback_reason"
                )

        if self.support_status in {
            DomainSupportStatus.GENERIC_FALLBACK,
            DomainSupportStatus.NEEDS_EVIDENCE,
            DomainSupportStatus.UNRESOLVED,
        }:
            if self.fallback_reason is None:
                raise ValueError(
                    "non-specialized routing requires fallback_reason"
                )

        if self.support_status in {
            DomainSupportStatus.NEEDS_EVIDENCE,
            DomainSupportStatus.UNRESOLVED,
        }:
            if not self.clarification_required:
                raise ValueError(
                    "needs_evidence/unresolved must require clarification"
                )

        if (
            self.canonical_domain
            != CanonicalBusinessDomain.OTHER
            and self.unsupported_domain_hint is not None
        ):
            raise ValueError(
                "unsupported_domain_hint is only valid for OTHER"
            )

        return self
```

---

# 4. Canonical 결과 예시

## 4.1 고깃집

```python
DomainRoutingResult(
    raw_business_type="고깃집",
    canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    support_status=DomainSupportStatus.SPECIALIZED,
    business_tags=[
        RoutingTagEvidence(
            tag="restaurant",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
        ),
        RoutingTagEvidence(
            tag="korean_bbq",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.96,
        ),
    ],
    scene_tags=[],
    style_tags=[],
    matched_aliases=["고깃집"],
    evidence_refs=["user_text:고깃집"],
    clarification_required=False,
    confidence=0.98,
)
```

중요:

```
scene_tags에 bbq_grill을 자동 추가하지 않는다.
```

---

## 4.2 숯불 삼겹살을 판매하는 고깃집

```python
DomainRoutingResult(
    raw_business_type="고깃집",
    canonical_domain=CanonicalBusinessDomain.FOOD_AND_BEVERAGE,
    support_status=DomainSupportStatus.SPECIALIZED,
    business_tags=[
        RoutingTagEvidence(
            tag="restaurant",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
        ),
        RoutingTagEvidence(
            tag="korean_bbq",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.98,
        ),
    ],
    scene_tags=[
        RoutingTagEvidence(
            tag="bbq_grill",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
            evidence_ref="user_text:숯불 삼겹살",
        ),
        RoutingTagEvidence(
            tag="charcoal_grill",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
            evidence_ref="user_text:숯불",
        ),
    ],
    style_tags=[],
    matched_aliases=["고깃집"],
    evidence_refs=[
        "user_text:고깃집",
        "user_text:숯불 삼겹살",
    ],
    clarification_required=False,
    confidence=0.99,
)
```

---

## 4.3 모호한 뷰티살롱

```python
DomainRoutingResult(
    raw_business_type="뷰티살롱",
    canonical_domain=CanonicalBusinessDomain.BEAUTY,
    support_status=DomainSupportStatus.NEEDS_EVIDENCE,
    business_tags=[
        RoutingTagEvidence(
            tag="beauty_service",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.93,
        ),
    ],
    scene_tags=[],
    style_tags=[],
    fallback_reason=(
        DomainFallbackReason.AMBIGUOUS_BEAUTY_SUBDOMAIN
    ),
    matched_aliases=["뷰티살롱"],
    evidence_refs=["user_text:뷰티살롱"],
    clarification_required=True,
    unresolved_questions=[
        "어떤 뷰티 서비스 또는 상품을 홍보하려는지 확인이 필요합니다.",
    ],
    confidence=0.82,
)
```

---

## 4.4 운동화 온라인 쇼핑몰

```python
DomainRoutingResult(
    raw_business_type="온라인 운동화 쇼핑몰",
    canonical_domain=CanonicalBusinessDomain.RETAIL,
    support_status=DomainSupportStatus.SPECIALIZED,
    business_tags=[
        RoutingTagEvidence(
            tag="ecommerce",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
        ),
        RoutingTagEvidence(
            tag="footwear_retail",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.94,
        ),
    ],
    scene_tags=[],
    style_tags=[],
    matched_aliases=["온라인 쇼핑몰"],
    evidence_refs=["user_text:온라인 운동화 쇼핑몰"],
    clarification_required=False,
    confidence=0.97,
)
```

---

## 4.5 헬스장

```python
DomainRoutingResult(
    raw_business_type="헬스장",
    canonical_domain=CanonicalBusinessDomain.OTHER,
    support_status=DomainSupportStatus.GENERIC_FALLBACK,
    unsupported_domain_hint="fitness",
    business_tags=[
        RoutingTagEvidence(
            tag="fitness",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.99,
        ),
        RoutingTagEvidence(
            tag="local_service",
            source=RoutingEvidenceSource.USER_TEXT,
            confidence=0.88,
        ),
    ],
    scene_tags=[],
    style_tags=[],
    fallback_reason=(
        DomainFallbackReason.UNSUPPORTED_DOMAIN_IN_MVP
    ),
    matched_aliases=["헬스장"],
    evidence_refs=["user_text:헬스장"],
    clarification_required=False,
    confidence=0.98,
)
```

---

# 5. 레거시 호환 계약

Canonical 결과에 `legacy_visual_key`를 넣지 않는다.

레거시 변환은 별도 모델과 adapter가 담당한다.

## 5.1 Legacy Key

```python
class LegacyVisualRouteKey(StrEnum):
    CAFE = "cafe"
    RESTAURANT = "restaurant"
    RESTAURANT_BBQ = "restaurant_bbq"

    BEAUTY_SKINCARE = "beauty_skincare"
    BEAUTY_HAIR = "beauty_hair"
    BEAUTY_NAIL = "beauty_nail"
    BEAUTY_SPA = "beauty_spa"

    GENERIC = "generic"
```

이 enum은 신규 비즈니스 로직에서 직접 사용하지 않는다.

---

## 5.2 Legacy Projection

```python
class LegacyRoutingProjection(BaseModel):
    projection_version: Literal["1.0"] = "1.0"

    route_key: LegacyVisualRouteKey

    reason_codes: list[str] = Field(
        default_factory=list,
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
    )

    fallback_used: bool = False
    fallback_reason: DomainFallbackReason | None = None

    deprecated: Literal[True] = True
```

---

## 5.3 Adapter 계약

```python
def project_to_legacy_visual_route(
    domain_result: DomainRoutingResult,
    *,
    product_tags: set[str],
    explicit_scene_tags: set[str],
) -> LegacyRoutingProjection:
    ...
```

규칙:

```
food_and_beverage + cafe
→ cafe

food_and_beverage + restaurant
→ restaurant

food_and_beverage
+ korean_bbq
+ grilled_meat 또는 bbq_grill evidence
→ restaurant_bbq

beauty + skincare evidence
→ beauty_skincare

beauty + hair evidence
→ beauty_hair

beauty + nail evidence
→ beauty_nail

beauty + spa evidence
→ beauty_spa

beauty + subtype evidence 없음
→ generic
→ fallback_reason=ambiguous_beauty_subdomain

retail
→ 현재 specialized legacy profile이 없으면 generic
→ fallback_reason=no_specialized_visual_profile

other
→ generic
→ 원래 fallback_reason 유지
```

핵심:

```
restaurant_bbq는 business tag 하나만으로 선택 금지
beauty subtype은 exact evidence 없이 선택 금지
```

---

# 6. Reference Template Routing 계약

## 6.1 신규 모델

```python
class ReferenceTemplateRoutingProfile(BaseModel):
    contract_version: Literal["1.0"] = "1.0"

    applies_to_all_domains: bool = False

    business_domains: set[CanonicalBusinessDomain] = Field(
        default_factory=set,
    )

    business_tags: set[str] = Field(
        default_factory=set,
    )
    product_tags: set[str] = Field(
        default_factory=set,
    )
    scene_tags: set[str] = Field(
        default_factory=set,
    )
    style_tags: set[str] = Field(
        default_factory=set,
    )
    placements: set[str] = Field(
        default_factory=set,
    )

    excluded_tags: set[str] = Field(
        default_factory=set,
    )

    @model_validator(mode="after")
    def validate_routing_profile(
        self,
    ) -> "ReferenceTemplateRoutingProfile":
        if (
            not self.applies_to_all_domains
            and not self.business_domains
            and not self.business_tags
            and not self.product_tags
            and not self.scene_tags
            and not self.style_tags
        ):
            raise ValueError(
                "routing profile requires at least one routing dimension"
            )

        included_tags = (
            self.business_tags
            | self.product_tags
            | self.scene_tags
            | self.style_tags
        )

        if included_tags & self.excluded_tags:
            raise ValueError(
                "included and excluded tags must not overlap"
            )

        return self
```

## 6.2 필드 정책

```
business_domains:
CanonicalBusinessDomain만 허용

business_tags:
cafe, restaurant, ecommerce, physical_store 등

product_tags:
dessert, beverage, skincare_product, footwear 등

scene_tags:
bbq_grill, tabletop, product_closeup, lifestyle 등

style_tags:
minimal, editorial, premium, pastel, traditional 등

placements:
instagram_feed, story, poster, hero 등
```

금지:

```
business_domains에 restaurant_bbq 저장
business_tags에 premium 저장
scene_tags에 cafe 저장
style_tags에 skincare 저장
"*" 문자열 wildcard 사용
```

전체 도메인 적용은:

```
applies_to_all_domains = true
```

로 표현한다.

---

# 7. 기존 필드 마이그레이션

현재 reference template의:

```
business_types
```

필드는 즉시 삭제하지 않는다.

전환 기간에는 다음 adapter를 둔다.

```python
def migrate_legacy_template_business_types(
    legacy_values: list[str],
) -> ReferenceTemplateRoutingProfile:
    ...
```

예:

```
cafe
→ business_domains={food_and_beverage}
→ business_tags={cafe}

restaurant_bbq
→ business_domains={food_and_beverage}
→ business_tags={restaurant, korean_bbq}
→ scene_tags={bbq_grill}

beauty_skincare
→ business_domains={beauty}
→ business_tags={skincare}

premium
→ style_tags={premium}
```

마이그레이션 결과에는 다음을 기록한다.

```
legacy_values
normalized_profile
unmapped_values
migration_warnings
```

매핑되지 않은 값을 조용히 버리면 안 된다.

---

# 8. SSOT 함수 계약

`domain_routing.py`가 제공해야 할 외부 함수는 다음으로 고정한다.

```python
def normalize_business_type(
    raw_business_type: str | None,
    *,
    evidence: list[RoutingTagEvidence] | None = None,
) -> DomainRoutingResult:
    ...
```

```python
def is_specialized_domain(
    domain: CanonicalBusinessDomain,
) -> bool:
    ...
```

```python
def project_to_legacy_visual_route(
    domain_result: DomainRoutingResult,
    *,
    product_tags: set[str],
    explicit_scene_tags: set[str],
) -> LegacyRoutingProjection:
    ...
```

```python
def normalize_reference_template_routing(
    *,
    business_domains: set[str] | None = None,
    business_tags: set[str] | None = None,
    product_tags: set[str] | None = None,
    scene_tags: set[str] | None = None,
    style_tags: set[str] | None = None,
    placements: set[str] | None = None,
) -> ReferenceTemplateRoutingProfile:
    ...
```

기존 compatibility 함수는 내부에서 위 함수를 호출해야 한다.

```
BUSINESS_TYPE_MAP
to_canonical_domain
select_visual_preset
select_visual_template
```

각 함수가 독립적으로 alias를 다시 해석하면 안 된다.

---

# 9. 금지되는 설계

## 9.1 Canonical enum에 세부 상품 추가

```
macaron
cheesecake
strawberry_latte
serum
sneakers
```

금지.

## 9.2 Canonical enum에 scene 추가

```
restaurant_bbq
charcoal_grill
product_closeup
```

금지.

## 9.3 모호한 beauty 자동 변환

```
beauty_salon → skincare
beauty_salon → hair
```

금지.

## 9.4 미지원 업종 정보 삭제

```
fitness → other
원래 fitness였다는 기록 없음
```

금지.

## 9.5 Reference template tag 혼합

```python
business_types=[
    "cafe",
    "premium",
    "bbq_grill",
]
```

금지.

---

# 10. 필수 불변 조건

```
INV-01:
모든 입력은 canonical_domain을 가진다.

INV-02:
specialized가 아니면 fallback_reason이 존재한다.

INV-03:
needs_evidence/unresolved이면 clarification_required=true다.

INV-04:
restaurant_bbq는 canonical domain이 아니다.

INV-05:
bbq_grill은 scene evidence 없이 생성되지 않는다.

INV-06:
beauty subtype은 exact evidence 없이 생성되지 않는다.

INV-07:
retail은 MVP specialized domain이다.

INV-08:
fitness/education/service는 OTHER로 가더라도 원래 hint를 보존한다.

INV-09:
Reference template의 domain/tag/style/scene 축은 분리한다.

INV-10:
Canonical routing result는 legacy preset/template ID를 포함하지 않는다.
```

---

# 11. 필수 테스트 계약

## Canonical completeness

```
food_and_beverage
beauty
retail
other
```

모두 정상 validation.

## Legacy input normalization

```
cafe
restaurant
beauty
retail
fitness
education
service
other
```

각 입력의 명시적 결과 존재.

## BBQ 분리

```
고깃집 + 감자튀김
→ restaurant_bbq 아님

고깃집 + 숯불 삼겹살
→ restaurant_bbq 가능
```

## Beauty ambiguity

```
뷰티살롱
→ needs_evidence

세럼
→ beauty + skincare

네일샵
→ beauty + nail

헤어샵
→ beauty + hair

눈썹 시술
→ beauty + eyebrow
```

`eyebrow` 전용 legacy preset이 없다면 canonical tag는 유지하고 legacy generic fallback으로 보낸다.

## Unsupported domain preservation

```
헬스장
→ other
→ unsupported_domain_hint=fitness

학원
→ other
→ unsupported_domain_hint=education

세무 상담
→ other
→ unsupported_domain_hint=professional_service
```

## Reference metadata separation

```
restaurant_bbq legacy value
→ food_and_beverage domain
→ restaurant/korean_bbq business tags
→ bbq_grill scene tag
```

## Registry contract

```
LegacyRoutingProjection.route_key
→ 실제 preset 존재
→ 실제 template 존재
→ ScenePlan 허용값과 호환
```

---

# 12. 구현 순서

## Phase 1 — 계약 고정

```
CanonicalBusinessDomain
DomainSupportStatus
DomainFallbackReason
RoutingTagEvidence
DomainRoutingResult
LegacyRoutingProjection
ReferenceTemplateRoutingProfile
```

## Phase 2 — 기존 SSOT 보완

```
현재 7종 canonical 정의
→ MVP 3종 + other로 변경

restaurant_bbq
→ legacy projection 및 scene tag로 이동

beauty_salon
→ needs_evidence로 변경

fitness/education/service
→ other + unsupported_domain_hint

retail
→ specialized 유지
```

## Phase 3 — 입력 경계 연결

```
brief_interpreter
→ normalize_business_type()
```

## Phase 4 — 레거시 projection 연결

```
DomainRoutingResult
→ project_to_legacy_visual_route()
→ preset/template 동일 route_key
```

## Phase 5 — Reference metadata 분리

```
business_types
→ domain/tag/scene/style/placement 필드로 migration
```

---

# 13. 팀 합의 요약

| 결정 항목 | 최종 결정 |
| --- | --- |
| MVP canonical domain | F&B, Beauty, Retail, Other |
| Cafe/Restaurant | F&B 하위 business tag |
| restaurant_bbq | 업종에서 제거, scene/legacy key로 분리 |
| beauty_salon | Beauty는 확정, subtype은 evidence 요구 |
| fitness | Other + explicit generic fallback |
| education | Other + explicit generic fallback |
| service | Other + explicit generic fallback |
| retail | MVP specialized domain |
| Reference metadata | domain과 business/product/scene/style tag를 별도 필드로 저장 |
| Legacy key | canonical 결과에서 제거, adapter 결과에만 보존 |
| Generic fallback | fallback reason과 원래 domain hint 필수 |
| LLM 역할 | 의미·태그 추출 |
| Resolver 역할 | preset/template/strategy ID 선택 |

---

# 14. 최종 판단

공용 계약은 다음처럼 이해하면 된다.

```
CanonicalBusinessDomain
= 지원 정책을 결정하는 안정적인 상위 분류

business_tags
= 업종·매장·서비스 세부 의미

scene_tags
= 불판·숯불·테이블·스튜디오 같은 장면 의미

style_tags
= premium·minimal·pastel 같은 미학

LegacyRoutingProjection
= 기존 preset/template를 유지하기 위한 임시 호환 결과
```

가장 중요한 결정은 다음 두 가지다.

```
restaurant_bbq를 canonical domain에서 제거한다.

beauty_salon을 skincare로 자동 변환하지 않는다.
```

이 두 원칙이 지켜져야 현재의 하드코딩 수정이 단기 버그 패치가 아니라 실제 SSOT 전환 작업이 된다.

---

# 2. 전체적으로 필요한 기능

## 2.1 Domain Normalization SSOT

담당: 기존 SSOT 작업자

필요 기능:

```python
normalize_business_type(raw_value: str | None) -> DomainRoutingResult

to_canonical_domain(raw_value: str | None) -> CanonicalBusinessDomain

to_legacy_visual_key(
    domain: CanonicalBusinessDomain,
    *,
    business_tags: list[str] | None = None,
) -> LegacyVisualRouteKey

is_supported_domain(domain: CanonicalBusinessDomain) -> bool
```

### 정상화 정책

```
정확한 canonical 값
→ 그대로 사용

안정적인 alias
→ canonical domain으로 정규화

미지원이지만 식별 가능한 업종
→ canonical domain 보존
→ generic fallback 명시

해석 불가능
→ other/unresolved
```

### 잘못된 예

```python
if "salon" in value:
    return "beauty_hair"
```

### 권장 예

```python
EXACT_DOMAIN_ALIASES = {
    "고깃집": CanonicalBusinessDomain.RESTAURANT,
    "음식점": CanonicalBusinessDomain.RESTAURANT,
    "헤어샵": CanonicalBusinessDomain.BEAUTY,
    "네일샵": CanonicalBusinessDomain.BEAUTY,
}
```

단, alias는 상위 업종 정규화까지만 수행한다.

```
헤어샵 → beauty
네일샵 → beauty
고깃집 → restaurant
```

세부 visual subtype은 별도 태그로 남긴다.

```
business_tags=["hair_service"]
business_tags=["nail_service"]
business_tags=["korean_bbq"]
```

---

## 2.2 Legacy Routing Adapter

담당: 기존 SSOT 작업자

현재 selector들이 새로운 canonical model을 즉시 이해하지 못하므로 호환 adapter가 필요하다.

```python
class LegacyRoutingAdapter:
    def resolve(
        self,
        domain_result: DomainRoutingResult,
        *,
        product_tags: list[str],
        business_tags: list[str],
    ) -> LegacyVisualRouteKey:
        ...
```

역할:

```
새 canonical domain
→ 기존 preset/template가 이해하는 key로 변환

기존 route key
→ 유지

fallback
→ 이유를 기록한 generic
```

이 adapter에는 새로운 비즈니스 정책을 넣지 않는다. Anti-Corruption Layer는 서로 다른 의미 모델을 번역하는 경계이고, 새로운 비즈니스 규칙이나 전체 orchestration을 넣는 곳이 아니다. (Microsoft Learn)

### 반드시 구분할 것

```
restaurant:
일반 음식점 업종

restaurant_bbq:
기존 비주얼 호환 key

beauty:
상위 업종

beauty_skincare:
기존 비주얼 호환 key
```

---

## 2.3 Single Resolved Key Pipeline

담당: 기존 SSOT 작업자

현재 문제는 template와 preset이 서로 다른 입력을 해석한다는 것이다.

현재:

```
raw context.business_type
→ select_visual_template()

resolved business type
→ select_visual_preset()
```

Phase 2에서는 다음처럼 변경해야 한다.

```
DomainRoutingResult
→ LegacyRoutingAdapter
→ resolved_visual_key
   ├─ get_visual_template(resolved_visual_key)
   └─ get_visual_preset(resolved_visual_key)
```

함수 책임도 바꿔야 한다.

```python
def get_visual_preset(
    route_key: LegacyVisualRouteKey,
) -> VisualPreset:
    ...
```

```python
def get_visual_template(
    route_key: LegacyVisualRouteKey,
) -> VisualTemplate:
    ...
```

삭제할 책임:

```
substring matching
raw user input 해석
한글 키워드 판별
beauty subtype 추론
business classification
```

즉 selector는 **분류기가 아니라 registry lookup 함수**가 되어야 한다.

---

## 2.4 Open-domain Business Context

담당: 두 번째 작업자

Canonical domain만으로는 고깃집 감자튀김 문제를 해결할 수 없다. 사업장, 상품, 씬을 분리한 모델이 필요하다.

```python
class BusinessEnvironmentContext(BaseModel):
    broad_domain: CanonicalBusinessDomain

    venue_type: str | None
    service_model: str | None

    business_tags: list[str]
    environment_tags: list[str]

    evidence_refs: list[str]
    confidence: float
```

예:

```python
BusinessEnvironmentContext(
    broad_domain="restaurant",
    venue_type="korean_bbq_restaurant",
    service_model="dine_in",
    business_tags=["korean_bbq"],
    environment_tags=["restaurant_table", "warm_interior"],
    evidence_refs=["user_text:고깃집"],
    confidence=0.97,
)
```

이 모델에는 다음을 넣으면 안 된다.

```
product_name
product cooking method
preset ID
template ID
headline
```

---

## 2.5 Product Visual Context

담당: 두 번째 작업자

기존 `ProductUnderstanding`을 비주얼 라우팅에 적합한 구조로 변환한다.

```python
class ProductVisualContext(BaseModel):
    product_name: str
    category_path: list[str]

    product_tags: list[str]
    visible_attributes: list[str]
    explicit_preparation_methods: list[str]

    permissible_visual_inferences: list[str]
    prohibited_visual_inferences: list[str]

    evidence_refs: list[str]
    confidence: float
```

### 감자튀김 예

```python
ProductVisualContext(
    product_name="감자튀김",
    category_path=[
        "food_and_beverage",
        "side_dish",
        "fried_potato",
    ],
    product_tags=[
        "fried_potato",
        "crispy_food",
        "side_dish",
    ],
    visible_attributes=[
        "golden_surface",
        "thin_cut",
    ],
    explicit_preparation_methods=["fried"],
    permissible_visual_inferences=[
        "crispy_surface",
        "serving_plate",
    ],
    prohibited_visual_inferences=[
        "charcoal",
        "open_flame",
        "grill_marks",
        "meat",
    ],
    confidence=0.95,
)
```

### 삼겹살 예

```python
product_tags=[
    "pork",
    "grilled_meat",
]

explicit_preparation_methods=[
    "table_grilled",
]

permissible_visual_inferences=[
    "grill",
    "charcoal",
    "smoke",
]
```

---

## 2.6 Creative Routing Context

담당: 두 번째 작업자

최종 resolver가 소비할 하나의 구조를 만든다.

```python
class CreativeRoutingContext(BaseModel):
    domain: DomainRoutingResult
    business: BusinessEnvironmentContext
    product: ProductUnderstanding
    product_visual: ProductVisualContext

    campaign: CampaignContext
    ad_format: AdFormatContract

    visual_observations: list[EvidenceItem]
    reference_style_profile: dict | None

    ambiguity_flags: list[str]
    input_conflicts: list[InputConflict]

    resolver_version: str
```

이 구조는 bounded context별 어휘를 혼합하지 않고 경계에서 조합하는 역할을 한다. DDD에서도 하나의 용어를 시스템 전역에서 무조건 같은 의미로 쓰기보다, bounded context별 언어를 분리하고 경계에서 연결하는 것이 중요하다. (Microsoft Learn)

---

## 2.7 Visual Semantic Intent 생성

담당: 두 번째 작업자

LLM/VLM은 내부 preset ID를 선택하는 것이 아니라 열린 의미를 구조화해야 한다.

```python
class VisualSemanticIntent(BaseModel):
    subject_priority: float
    environment_priority: float
    text_priority: float

    desired_moods: list[str]
    desired_materials: list[str]
    lighting_preferences: list[str]
    composition_preferences: list[str]

    required_visual_facts: list[str]
    prohibited_visual_elements: list[str]

    copy_presence_mode: str

    confidence: float
```

입력:

```
InputEvidenceBundle
ProductUnderstanding
BusinessEnvironmentContext
CampaignContext
AdFormatContract
```

출력 예:

```python
VisualSemanticIntent(
    subject_priority=0.88,
    environment_priority=0.32,
    text_priority=0.18,
    desired_moods=["appetizing", "clean", "casual_premium"],
    desired_materials=["ceramic_plate", "wood_table"],
    lighting_preferences=["warm_side_light"],
    composition_preferences=["product_closeup", "negative_space_top"],
    required_visual_facts=["fried_potato"],
    prohibited_visual_elements=[
        "charcoal",
        "grill",
        "meat",
        "open_flame",
    ],
    copy_presence_mode="minimal",
    confidence=0.91,
)
```

### LLM의 역할

```
열린 입력 해석
태그·의미·근거 구조화
불확실성 기록
```

### LLM이 하면 안 되는 일

```
preset ID 직접 생성
template ID 직접 생성
provider engine 결정
존재하지 않는 registry ID 발명
```

---

## 2.8 Visual Strategy Registry

담당: 두 번째 작업자

상품별 프리셋 목록이 아니라 **시각 전략 능력**을 등록한다.

```python
class VisualStrategyProfile(BaseModel):
    strategy_id: str
    archetype: str

    supported_domains: set[CanonicalBusinessDomain]
    supported_campaign_roles: set[str]
    supported_placements: set[str]

    required_tags: set[str]
    preferred_tags: set[str]
    excluded_tags: set[str]

    composition_template_id: str
    mood_preset_id: str
    copy_tone_profile_id: str

    provider_capabilities: set[str]

    priority: int
    enabled: bool
```

예:

```python
VisualStrategyProfile(
    strategy_id="food_product_editorial",
    archetype="product_editorial",
    supported_domains={
        CanonicalBusinessDomain.RESTAURANT,
        CanonicalBusinessDomain.CAFE,
        CanonicalBusinessDomain.RETAIL,
    },
    supported_campaign_roles={
        "product_promotion",
        "new_product_introduction",
    },
    required_tags=set(),
    preferred_tags={
        "prepared_food",
        "dessert",
        "beverage",
        "side_dish",
    },
    excluded_tags=set(),
    composition_template_id="product_editorial_clean",
    mood_preset_id="food_appetizing_natural",
    copy_tone_profile_id="product_minimal",
    provider_capabilities={
        "local_clean_visual",
        "gpt_image_native_copy",
    },
    priority=50,
    enabled=True,
)
```

BBQ 전략:

```python
VisualStrategyProfile(
    strategy_id="korean_bbq_grill_scene",
    archetype="dining_scene",
    supported_domains={
        CanonicalBusinessDomain.RESTAURANT,
    },
    required_tags={
        "korean_bbq",
        "grilled_meat",
    },
    preferred_tags={
        "charcoal",
        "table_grilled",
    },
    excluded_tags={
        "fried_potato_only",
        "beverage_only",
    },
    ...
)
```

핵심:

```
고깃집 태그 하나만으로 BBQ scene 선택 불가
상품 측 grilled_meat 근거가 함께 있어야 함
```

---

## 2.9 Visual Strategy Resolver

담당: 두 번째 작업자

```python
def resolve_visual_strategy(
    context: CreativeRoutingContext,
    intent: VisualSemanticIntent,
    registry: VisualStrategyRegistry,
) -> VisualStrategyDecision:
    ...
```

### 처리 단계

```
1. Provider/format capability로 후보 필터
2. required tag 충족 여부 검사
3. excluded/prohibited 요소 검사
4. 상품 근거 일치도 평가
5. 캠페인·포맷 적합도 평가
6. 사업 환경 적합도 평가
7. reference style 적합도 평가
8. fallback penalty 적용
9. 결정 및 trace 생성
```

### 점수 축

상품명별 점수를 만들면 안 된다.

```python
class VisualStrategyScore(BaseModel):
    evidence_alignment: float
    product_relevance: float
    campaign_fit: float
    format_fit: float
    environment_fit: float
    reference_fit: float
    unsupported_inference_penalty: float
    fallback_penalty: float
    total_score: float
```

### 핵심 불변 조건

```python
if strategy_requires_visual_element("grill"):
    require_explicit_or_visual_evidence("grilled")
```

더 일반적으로:

```
사업장 정보는 상품의 정체성·조리법·형태를 덮어쓸 수 없다.
```

---

## 2.10 Visual Strategy Decision

담당: 두 번째 작업자

```python
class VisualStrategyDecision(BaseModel):
    strategy_id: str
    route_version: str

    archetype: str

    composition_template_id: str
    mood_preset_id: str
    copy_tone_profile_id: str

    subject_guidance: list[str]
    environment_guidance: list[str]
    negative_constraints: list[str]

    matched_rules: list[str]
    rejected_strategy_ids: list[str]
    evidence_refs: list[str]

    confidence: float

    fallback_used: bool
    fallback_reason: str | None
```

이 결정 하나에서 다음이 함께 나와야 한다.

```
template
preset
copy tone
scene guidance
negative constraints
```

템플릿과 프리셋이 별도로 업종을 재해석하면 안 된다.

---

## 2.11 Strategy Integrity Validator

담당: 두 번째 작업자

```python
def validate_visual_strategy_registry(
    registry: VisualStrategyRegistry,
    *,
    presets: PresetRegistry,
    templates: TemplateRegistry,
    copy_profiles: CopyToneRegistry,
) -> RegistryValidationReport:
    ...
```

검사:

```
모든 strategy_id 고유
preset ID 존재
template ID 존재
copy tone profile 존재
archetype 유효
required와 excluded tag 충돌 없음
disabled profile 선택 불가
provider capability 유효
fallback profile 최소 1개 존재
```

Pydantic discriminated union을 활용하면 product/editorial, service/lifestyle, information/poster처럼 필수 필드가 다른 전략을 명시적으로 분리할 수 있다. (Pydantic Docs)

예:

```python
VisualStrategy = Annotated[
    ProductEditorialStrategy
    | ServiceLifestyleStrategy
    | InformationPosterStrategy,
    Field(discriminator="kind"),
]
```

---

## 2.12 Explicit Fallback Profiles

담당: 두 번째 작업자

`generic` 하나 대신 최소 다음 fallback이 필요하다.

```
generic_product_editorial
generic_service_lifestyle
generic_local_business
generic_information_poster
generic_brand_awareness
```

예:

```
retail + 운동화
→ generic_product_editorial

education + 영어 수업
→ generic_service_lifestyle

service + 세무 상담
→ generic_local_business

promotion + 정보 다수
→ generic_information_poster
```

반드시 기록:

```
fallback_used
fallback_reason
unsupported_domain
missing_specialized_profile
```

---

## 2.13 Shadow Routing 및 비교 기능

담당: 두 번째 작업자 구현

실제 production 연결: 기존 SSOT 작업자

```python
class RoutingMode(StrEnum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    CANONICAL = "canonical"
```

### LEGACY

```
기존 route 결과 사용
신규 resolver 미실행
```

### SHADOW

```
기존 route 결과로 실제 생성
신규 resolver 병렬 실행
결과 차이 trace에 기록
```

### CANONICAL

```
신규 VisualStrategyDecision으로 실제 생성
```

비교 결과:

```python
class RouteComparison(BaseModel):
    legacy_preset_id: str
    legacy_template_id: str

    new_strategy_id: str
    new_preset_id: str
    new_template_id: str

    preset_match: bool
    template_match: bool
    family_match: bool

    disagreement_codes: list[str]
    severity: str
```

Shadow migration은 기존 경로를 유지하면서 신규 경로의 결과를 관찰하고 점진적으로 전환하는 구조이므로 현재 strangler 접근과 잘 맞는다. (Microsoft Learn)

---

## 2.14 Visual Routing Trace

담당: 두 번째 작업자

```python
class VisualRoutingTrace(BaseModel):
    resolver_version: str
    routing_mode: RoutingMode

    raw_business_type: str | None
    canonical_domain: CanonicalBusinessDomain
    legacy_visual_key: LegacyVisualRouteKey | None

    product_name: str
    category_path: list[str]

    business_tags: list[str]
    product_tags: list[str]
    campaign_role: str
    placement: str

    selected_strategy_id: str
    selected_template_id: str
    selected_preset_id: str
    selected_copy_tone_profile_id: str

    matched_rules: list[str]
    rejected_rules: list[str]

    fallback_used: bool
    fallback_reason: str | None

    route_disagreement: RouteComparison | None
```

이 trace는 다음 문제를 구분하기 위해 필요하다.

```
ProductUnderstanding 오분류
business normalization 오류
strategy resolver 오류
template/preset registry 오류
provider prompt adapter 오류
이미지 모델 자체 hallucination
```

---

## 2.15 Provider Prompt Adapter

Phase 2–3 병행 작업이 끝난 뒤 통합 작업으로 진행한다.

### Local visual adapter

```python
def build_local_visual_prompt(
    strategy: VisualStrategyDecision,
    product: ProductVisualContext,
) -> LocalVisualPrompt:
    ...
```

정책:

```
이미지 내부 텍스트 기본 금지
상품 중심
pseudo text negative prompt
negative space 확보
strategy의 subject/environment/negative guidance 사용
```

### GPT Image 2 native adapter

```python
def build_gpt_image2_native_prompt(
    strategy: VisualStrategyDecision,
    approved_copy: NativeCopyBrief,
) -> GPTImageNativePrompt:
    ...
```

정책:

```
승인된 headline/support만 전달
raw user request 전달 금지
preset ID 전달 금지
이미지 호출 1회
edit/retry 0
external renderer 0
```

Provider adapter 안에는 업종별 if문을 넣지 않는다.

---

# 3. 두 명의 병행 작업 분할

## 작업자 A — Domain Routing SSOT 및 Legacy Path 통합

현재 SSOT를 진행 중인 팀원이 그대로 담당한다.

### 담당 범위

```
Phase 0 버그 수정 마무리
Phase 1 SSOT 계약 고정
Phase 2 single resolved key pipeline
legacy adapter
legacy routing observability
기존 경로 회귀 방지
최종 production wiring
```

### 소유 파일

```
orchestrator/app/llm/domain_routing.py
orchestrator/app/llm/nodes/brief_interpreter.py
orchestrator/app/llm/scene_planner.py
orchestrator/app/llm/visual_presets.py
orchestrator/app/llm/visual_templates.py
orchestrator/app/llm/copy_tone_policy.py

orchestrator/tests/test_domain_routing.py
orchestrator/tests/test_domain_routing_contract.py
```

### 구체 작업

### A-1. 공용 계약 확정

```
CanonicalBusinessDomain
LegacyVisualRouteKey
DomainSupportStatus
DomainRoutingResult
```

### A-2. Canonical/legacy 분리

```
restaurant_bbq를 canonical domain에서 제외
beauty_skincare/hair/nail/spa를 canonical domain에서 제외
legacy compatibility key로 명시
```

### A-3. Silent drop 제거

```
retail
education
service
fitness

→ canonical domain 보존
→ explicit generic fallback
→ fallback_reason 기록
```

### A-4. Exact mapping

```
selector substring 제거
exact key lookup
unsupported key fail-closed 또는 explicit fallback
```

### A-5. Single resolved key

```
brief_interpreter
→ domain result
→ legacy visual adapter
→ preset/template 동일 key 사용
```

### A-6. Copy tone 회귀 방지

```
restaurant → restaurant_bbq 제거
business domain과 product/campaign tone 분리 전까지 neutral fallback
```

### A-7. Contract tests

```
모든 BriefBusinessType 정규화 결과 존재
모든 legacy key의 preset/template 존재
preset business key가 ScenePlan 허용값과 일치
beauty_salon hair 오라우팅 없음
restaurant BBQ tone 오라우팅 없음
silent generic 없음
```

### A-8. 통합 wiring 소유

작업자 B가 만든 신규 resolver를 production `scene_planner`에 연결하는 최종 integration은 작업자 A가 수행한다.

이유:

```
scene_planner/visual_presets/visual_templates를 A가 소유하므로
동시 수정 conflict를 방지
```

---

## 작업자 B — Open-domain Creative Context 및 Visual Strategy Shadow

작업자 A의 공용 계약을 소비하되 A 소유 파일은 수정하지 않는다.

### 담당 범위

```
Business/Product/Scene/Campaign 축 분리
CreativeRoutingContext
VisualSemanticIntent
VisualStrategyRegistry
VisualStrategyResolver
fallback profile
routing trace
shadow comparator
cross-domain tests
benchmark runner
```

### 소유 파일 권장

```
orchestrator/app/schemas/business_context.py
orchestrator/app/schemas/creative_routing.py
orchestrator/app/schemas/visual_strategy.py

orchestrator/app/llm/business_context_service.py
orchestrator/app/llm/product_visual_context.py
orchestrator/app/llm/visual_semantic_intent_service.py
orchestrator/app/llm/visual_strategy_registry.py
orchestrator/app/llm/visual_strategy_resolver.py
orchestrator/app/llm/visual_strategy_validator.py
orchestrator/app/llm/visual_routing_trace.py
orchestrator/app/llm/visual_route_comparator.py
```

테스트:

```
orchestrator/tests/test_business_context.py
orchestrator/tests/test_product_visual_context.py
orchestrator/tests/test_visual_strategy_registry.py
orchestrator/tests/test_visual_strategy_resolver.py
orchestrator/tests/test_visual_routing_invariants.py
orchestrator/tests/test_visual_routing_shadow.py
```

### B가 수정하지 않을 파일

```
domain_routing.py
brief_interpreter.py
scene_planner.py
visual_presets.py
visual_templates.py
copy_tone_policy.py
image_prompt_v3.py
```

`image_prompt_v3.py` 변경이 필요하면 별도 integration 단계로 넘긴다.

### 구체 작업

### B-1. Multi-axis schema

```
BusinessEnvironmentContext
ProductVisualContext
CreativeRoutingContext
VisualSemanticIntent
VisualStrategyDecision
VisualRoutingTrace
```

### B-2. Evidence merger

```python
build_business_environment_context(...)
build_product_visual_context(...)
build_creative_routing_context(...)
```

### B-3. Product-over-business invariant

```
사업장 태그만으로 상품 조리법을 생성하지 않음
명시적 사용자 사실 또는 이미지 근거 필요
```

### B-4. Registry

```
capability 기반 profile
required/preferred/excluded tags
template/preset/copy profile reference
provider capability
fallback profile
```

### B-5. Resolver

```
후보 필터
금지 추론 제거
generic score
결정
fallback
trace
```

### B-6. Shadow comparator

```
legacy preset/template
vs
new strategy preset/template

불일치 코드
심각도
fallback 차이
```

### B-7. Cross-domain test

최소:

```
고깃집 + 감자튀김
고깃집 + 삼겹살
카페 + 치즈케이크
카페 + 딸기라떼
식당 + 된장찌개
뷰티숍 + 세럼
온라인 소매 + 운동화
학원 + 영어 수업
헬스장 + 회원권
전문 서비스 + 세무 상담
```

### B-8. Metamorphic test

```
상품은 동일
업종만 변경

→ 상품 정체성 유지
→ 환경 guidance만 변경
→ 근거 없는 조리법 생성 없음
```

---

# 4. 병행 작업을 위한 브랜치 전략

현재 작업자 A의 SSOT Phase 0–1 commit을 기준점으로 사용한다.

## 권장 구조

```
A branch:
feat/domain-routing-ssot-phase2

B branch:
feat/visual-strategy-shadow-v1
```

B 브랜치는 A의 `DomainRoutingResult` 계약이 들어간 commit에서 분기하는 **stacked branch**가 적절하다.

```
develop
└─ A Phase 0–1 contract commit
   ├─ A Phase 2 branch
   └─ B Visual Strategy branch
```

병합 순서:

```
1. A Phase 0–1/2 PR merge
2. B branch를 최신 develop에 rebase
3. B 신규 schema/resolver PR merge
4. A가 integration branch 생성
5. scene_planner에 shadow wiring
6. shadow 결과 검증
7. canonical cutover
```

작업자 B가 A의 미완성 함수 구현에 의존하면 안 된다.

B가 의존할 것은 오직 다음뿐이다.

```
CanonicalBusinessDomain
LegacyVisualRouteKey
DomainRoutingResult
```

---

# 5. 두 작업자 간 공통 합의 사항

## 합의 1. Canonical domain은 작고 안정적으로 유지

```
상품명 추가 금지
visual scene 추가 금지
provider engine 추가 금지
campaign role 추가 금지
```

## 합의 2. Open vocabulary는 태그와 category_path로 처리

```
치즈케이크
감자튀김
세럼
운동화
영어 수업
세무 상담
```

이를 enum에 추가하지 않는다.

## 합의 3. 내부 ID는 LLM이 만들지 않음

```
LLM:
semantic tags

Resolver:
strategy/template/preset ID
```

## 합의 4. Selector는 분류하지 않음

```
get_visual_preset(id)
get_visual_template(id)
```

lookup만 담당한다.

## 합의 5. Fallback은 오류를 숨기지 않음

```
fallback_used
fallback_reason
support_status
```

필수 기록.

## 합의 6. 실제 route 변경은 shadow 이후

```
첫 PR:
관찰만

다음 PR:
일부 route cutover

최종:
legacy selector 제거
```

---

# 6. 통합 단계

두 작업자의 PR이 모두 반영된 후 별도 integration 작업이 필요하다.

## Integration 1 — Shadow Wiring

작업자 A 담당.

```
scene_planner
→ legacy route 실행
→ new strategy resolver 실행
→ 실제 출력은 legacy 사용
→ comparison trace 저장
```

완료 기준:

```
production output 변화 없음
legacy/new 결과 모두 기록
preset/template mismatch 측정 가능
fallback rate 측정 가능
```

## Integration 2 — Canonical Cutover

다음 조건 이후 진행한다.

```
registry integrity 통과
cross-domain tests 통과
shadow mismatch 검토 완료
critical mismatch 0
fallback reason 누락 0
```

처음부터 전체를 전환하지 않고 범위를 제한한다.

```
1. cafe/restaurant visual-first
2. beauty product
3. retail/product fallback
4. education/service
5. fitness/service
```

## Integration 3 — Legacy 제거

사용처 0 확인 후 제거:

```
BUSINESS_TYPE_MAP의 중복값
resolve_business_type
resolve_beauty_subtype
substring preset selector
substring template selector
copy tone alias map
dead marketing.BusinessType
```

---

# 7. 최종 완료 기준

## 구조

```
- canonical business domain SSOT 1개
- legacy route key 명시적 분리
- business/product/scene/campaign 축 분리
- raw business string의 downstream 직접 전달 없음
- preset/template 독립 라우팅 없음
- product별 production if문 없음
- duplicated Korean keyword set 없음
```

## 기능

```
- restaurant와 restaurant_bbq 구분
- beauty와 beauty subtype 구분
- fitness/retail/education/service 증발 없음
- unsupported domain fallback reason 존재
- 감자튀김에 근거 없는 불판 금지
- 삼겹살에는 근거가 있을 때 grill 허용
- 세럼이 hair salon preset으로 오라우팅되지 않음
- template/preset/copy tone가 하나의 decision에서 결정
```

## 관측성

```
- canonical domain
- legacy visual key
- strategy ID
- preset/template ID
- matched/rejected rules
- fallback
- legacy/new disagreement
```

## 테스트

```
- taxonomy completeness
- registry integrity
- product-over-business invariant
- explicit evidence override
- open-domain holdout
- metamorphic tests
- silent fallback guard
- GPT Image 2 과거 regression
```

---

## 최종 작업 분담 요약

| 영역 | 작업자 A: SSOT | 작업자 B: Visual Strategy |
| --- | --- | --- |
| Canonical business domain | 담당 | 소비 |
| Brief normalization | 담당 | 제외 |
| Legacy visual adapter | 담당 | 제외 |
| Preset/template key 통일 | 담당 | 제외 |
| Scene planner wiring | 담당 | 제외 |
| Business environment schema | 제외 | 담당 |
| Product visual context | 제외 | 담당 |
| Visual semantic intent | 제외 | 담당 |
| Strategy registry | 제외 | 담당 |
| Strategy resolver | 제외 | 담당 |
| Fallback profiles | 협의 | 담당 |
| Shadow comparator | 연결 | 구현 |
| Routing trace | 연결 | 구현 |
| Provider adapter | 통합 단계 | 초안/순수 함수 |
| Production cutover | 담당 | 검증 지원 |
| Cross-domain benchmark | 지원 | 담당 |

이 분할의 핵심은 **작업자 A가 기존 실행 경로와 전환 경계를 소유하고, 작업자 B가 기존 경로를 건드리지 않은 채 새로운 의미 모델과 resolver를 순수 모듈로 구축하는 것**이다. 이렇게 해야 두 사람이 실제로 병행할 수 있고, `scene_planner.py`, `visual_presets.py`, `visual_templates.py`에서 반복 충돌하는 상황을 피할 수 있다.