from __future__ import annotations

from orchestrator.app.llm.schemas.image_prompt_v3 import ScenePlan, PromptQualityPolicy, EnginePromptAdapterOutput
COMMON_AD_PROMPT_CONSTRAINTS = (
    "Create a text-free advertising background for later Korean copy overlay. "
    "Reserve clean negative space for Korean text overlay in post-processing. "
    "Keep reserved text areas uncluttered, smooth, low-detail, and visually calm. "
    "Do not include any text, letters, words, numbers, logos, signage, labels, watermark, or typography."
)

def render_gpt_image_2_prompt(
    scene_plan: ScenePlan,
    policy: PromptQualityPolicy,
    preset_id: str | None = None,
    engine: str = "gpt_image_2",
) -> EnginePromptAdapterOutput:
    """Render a creative brief style prompt for OpenAI GPT-image engines."""
    reserved = scene_plan.reserved_copy_area
    subject_side = "right"
    if reserved in ["right", "upper_right", "lower_right"]:
        subject_side = "left"
    elif reserved in ["center"]:
        subject_side = "surrounding boundary"
        
    moods = ", ".join(scene_plan.desired_mood)
    props = ", ".join(scene_plan.secondary_props)
    
    prompt = (
        f"{COMMON_AD_PROMPT_CONSTRAINTS} "
        f"Create a premium realistic advertising background for {scene_plan.business_type}. "
        f"The main subject is {scene_plan.primary_subject}. "
        f"Place the main subject on the {subject_side} and keep a clean, uncluttered {reserved} negative space. "
        f"Use {moods}. Secondary props: {props}. "
        f"This image is intended for later Korean copy overlay."
    )
    
    return EnginePromptAdapterOutput(
        engine=engine,
        prompt=prompt,
        negative_prompt=None,
        engine_fit_score=1.0,
        warnings=[],
        metadata={
            "adapter_version": "v3",
            "subject_placement": subject_side,
            "reserved_copy_area": reserved,
            "preset_id": preset_id,
        }
    )


def render_sd35_large_prompt(
    scene_plan: ScenePlan,
    policy: PromptQualityPolicy,
    preset_id: str | None = None,
) -> EnginePromptAdapterOutput:
    """Render commercial photography tags with explicit negative prompts for SD3.5."""
    moods = ", ".join(scene_plan.desired_mood)
    
    positive = (
        f"{COMMON_AD_PROMPT_CONSTRAINTS} "
        f"premium commercial photography, {scene_plan.business_type} ad background, "
        f"{scene_plan.primary_subject}, {moods}, clean copy space"
    )
    
    negative_terms = [
        "text", "letters", "words", "Korean text", "logo", "watermark", 
        "menu board", "label", "price tag", "caption", "typography", 
        "blurry", "low quality", "cluttered"
    ]
    for term in policy.fake_text_negative_terms:
        if term not in negative_terms:
            negative_terms.append(term)
            
    negative = ", ".join(negative_terms)
    
    return EnginePromptAdapterOutput(
        engine="sd35_large",
        prompt=positive,
        negative_prompt=negative,
        engine_fit_score=0.9,
        warnings=[],
        metadata={
            "adapter_version": "v3",
            "engine": "sd35_large",
            "preset_id": preset_id,
        }
    )


def render_flux_prompt(scene_plan: ScenePlan,
    policy: PromptQualityPolicy,
    preset_id: str | None = None,
) -> EnginePromptAdapterOutput:
    """Render a dense positive prompt for Flux, using safe wordings to avoid text."""
    moods = ", ".join(scene_plan.desired_mood)
    props = ", ".join(scene_plan.secondary_props)
    
    prompt = (
        f"{COMMON_AD_PROMPT_CONSTRAINTS} "
        f"A premium realistic advertising background for {scene_plan.business_type} with clean unmarked surfaces, "
        f"blank negative space for later copy overlay, no visible writing or signage. "
        f"The main subject is {scene_plan.primary_subject}. "
        f"Props: {props}. Mood: {moods}. Soft commercial lighting, clean composition."
    )
    
    return EnginePromptAdapterOutput(
        engine="flux",
        prompt=prompt,
        negative_prompt=None,
        engine_fit_score=0.95,
        warnings=[],
        metadata={
            "adapter_version": "v3",
            "engine": "flux",
            "preset_id": preset_id,
            "flux_negative_policy": "positive_substitution",
        }
    )


def render_engine_prompt(
    engine: str,
    scene_plan: ScenePlan,
    policy: PromptQualityPolicy,
    preset_id: str | None = None,
) -> EnginePromptAdapterOutput:
    """Dispatches rendering to the proper engine adapter."""
    engine_lower = (engine or "").lower()
    engine_key = engine_lower.replace("-", "_")
    if "gpt" in engine_key or "openai" in engine_key or engine_key in {"gpt_image_1", "gpt_image_2"}:
        engine_name = "gpt_image_1" if engine_key in {"gpt_image_1", "gpt_image1"} else "gpt_image_2"
        return render_gpt_image_2_prompt(scene_plan, policy, preset_id=preset_id, engine=engine_name)
    elif "sd3" in engine_lower or "sd35" in engine_lower or "stability" in engine_lower or engine_lower == "sd35_large":
        return render_sd35_large_prompt(scene_plan, policy, preset_id=preset_id)
    elif "flux" in engine_lower:
        return render_flux_prompt(scene_plan, policy, preset_id=preset_id)
    else:
        # Fallback to gpt_image_1 prompt layout
        out = render_gpt_image_2_prompt(scene_plan, policy, preset_id=preset_id, engine="gpt_image_1")
        out.warnings.append(f"Unknown engine '{engine}', fallback to gpt_image_1 prompt layout.")
        return out
