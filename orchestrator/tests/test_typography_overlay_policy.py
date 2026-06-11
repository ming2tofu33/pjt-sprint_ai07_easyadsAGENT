from orchestrator.app.llm.nodes.typography_art_director import select_typography_art_direction


def test_menu_discovery_blocks_large_button_cta():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "cafe", "promotion_goal": "menu_discovery"},
            "copy_visual_intent": {"typography_mood": "premium_serif", "cta_visibility": "required"},
        }
    )
    assert direction.cta_treatment in {"text_link", "editorial_underline"}


def test_reservation_allows_small_chip():
    direction = select_typography_art_direction(
        {
            "context": {"business_type": "restaurant_bbq", "promotion_goal": "reservation"},
            "copy_visual_intent": {"typography_mood": "clean_sans", "cta_visibility": "required"},
        }
    )
    assert direction.cta_treatment == "small_chip"
