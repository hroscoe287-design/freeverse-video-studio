import json
from pathlib import Path

from app.core.comfyui_pipeline import _replace_tokens
from app.core.roscoe_anime_engine import (
    ENGINE_NAME,
    MODEL_PROFILES,
    build_scene_prompt,
    build_motion_prompt,
    engine_status,
)


def test_engine_registers_open_weight_image_and_video_models():
    assert ENGINE_NAME == "ROSCOE AI ANIME ENGINE"
    assert MODEL_PROFILES["image"]["license"] == "Apache-2.0"
    assert MODEL_PROFILES["video"]["license"] == "Apache-2.0"
    assert MODEL_PROFILES["image"]["id"] == "neta-art/Neta-Lumina"
    assert MODEL_PROFILES["video"]["id"] == "Wan-AI/Wan2.2-TI2V-5B"


def test_bloodline_prompt_adds_known_character_continuity():
    prompt = build_scene_prompt(
        "BLOODLINE Episode 1",
        "Diamond and Eternity Infinity face Murder Co.",
        "The Legacy",
        "Diamond enters the ruined temple."
    )
    assert "Cinematic Japanese 2D dark-fantasy anime" in prompt
    assert "Diamond: young male warrior, black hair, glowing red eyes" in prompt
    assert "Eternity Infinity" in prompt
    assert "Murder Co." in prompt


def test_motion_prompt_requests_continuous_shot():
    prompt = build_motion_prompt("A hero stands in the rain.", 5)
    assert "5.0-second anime shot" in prompt
    assert "no cuts" in prompt
    assert "no flicker" in prompt


def test_engine_readiness_requires_both_workflows_and_reachable_host():
    assert engine_status(True, True, True)["ready"] is True
    assert engine_status(True, True, False)["ready"] is False
    assert engine_status(False, True, True)["ready"] is False


def test_bundled_api_workflows_have_required_prompt_tokens():
    root = Path(__file__).resolve().parents[1] / "workflows"
    image = json.loads((root / "roscoe_neta_lumina_api.json").read_text())
    video = json.loads((root / "roscoe_wan22_i2v_api.json").read_text())
    image_text = json.dumps(image)
    video_text = json.dumps(video)
    assert "__PROMPT__" in image_text
    assert "__NEGATIVE_PROMPT__" in image_text
    assert "__PROMPT__" in video_text
    assert "__NEGATIVE_PROMPT__" in video_text
    assert "__IMAGE__" in video_text
    assert any(node.get("class_type") == "SaveImage" for node in image.values())
    assert any(node.get("class_type") == "SaveVideo" for node in video.values())


def test_workflow_seed_token_stays_numeric():
    result = _replace_tokens(
        {"1": {"inputs": {"seed": "__SEED__", "text": "__PROMPT__"}}},
        "anime hero", "bad anatomy", 12345, "keyframe.png"
    )
    assert result["1"]["inputs"]["seed"] == 12345
    assert isinstance(result["1"]["inputs"]["seed"], int)
    assert result["1"]["inputs"]["text"] == "anime hero"



def test_adaptive_engine_selects_anime_model_with_live_workers():
    from app.core.ai_horde_engine import choose_anime_model
    models = [
        {"name": "General SDXL", "count": 20, "performance": 90, "queued": 0},
        {"name": "Animagine XL 4.0", "count": 4, "performance": 35, "queued": 2},
        {"name": "NoobAI-XL", "count": 1, "performance": 10, "queued": 20},
    ]
    assert choose_anime_model(models) == "Animagine XL 4.0"


def test_adaptive_engine_uses_fewer_steps_for_distilled_models():
    from app.core.ai_horde_engine import adaptive_params
    lightning = adaptive_params("Anime Lightning XL")
    standard = adaptive_params("Animagine XL")
    assert lightning["steps"] == 8
    assert standard["steps"] == 24
    assert lightning["width"] % 64 == 0
    assert standard["height"] % 64 == 0


def test_adaptive_prompt_preserves_character_bible_and_scene():
    from app.core.ai_horde_engine import build_anime_prompt
    prompt = build_anime_prompt(
        "Diamond runs through a ruined temple.",
        "Diamond: black hair, glowing red eyes, dark coat."
    )
    assert "CHARACTER CONTINUITY" in prompt
    assert "black hair, glowing red eyes" in prompt
    assert "Diamond runs through a ruined temple" in prompt
    assert "single coherent frame" in prompt
