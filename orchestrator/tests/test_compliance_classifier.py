"""IndustryClassifier — business_type → compliance domain 매핑 테스트."""


def _cls():
    from orchestrator.app.compliance.industry_classifier import IndustryClassifier
    return IndustryClassifier()


def test_cafe_maps_to_food_and_general():
    domains = _cls().get_domains("cafe")
    assert "food" in domains
    assert "general_ad" in domains


def test_restaurant_maps_to_food():
    domains = _cls().get_domains("restaurant")
    assert "food" in domains


def test_beauty_skincare_maps_to_cosmetic():
    domains = _cls().get_domains("beauty_skincare")
    assert "cosmetic" in domains
    assert "general_ad" in domains


def test_hospital_maps_to_medical():
    domains = _cls().get_domains("hospital")
    assert "medical" in domains


def test_fitness_maps_to_general_ad():
    domains = _cls().get_domains("fitness")
    assert "general_ad" in domains


def test_unknown_type_falls_back_to_general_ad():
    domains = _cls().get_domains("unknown_xyz")
    assert domains == ["general_ad"]


def test_none_falls_back_to_general_ad():
    domains = _cls().get_domains(None)
    assert domains == ["general_ad"]


def test_all_food_business_types_include_food_domain():
    from orchestrator.app.compliance.industry_classifier import BUSINESS_TYPE_TO_DOMAIN

    food_types = [bt for bt, domains in BUSINESS_TYPE_TO_DOMAIN.items() if "food" in domains]
    assert len(food_types) >= 3


def test_get_domains_always_returns_list():
    cls = _cls()
    for biz_type in ["cafe", "hospital", "unknown", None]:
        result = cls.get_domains(biz_type)
        assert isinstance(result, list)
        assert len(result) > 0
