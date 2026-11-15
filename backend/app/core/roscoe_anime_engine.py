"""Roscoe Anime Engine: model registry and BLOODLINE prompt conditioning.

The engine is an orchestration layer over downloadable open-weight models.
It does not claim that model weights are bundled in this source repository.
"""
import os
from pathlib import Path
from typing import Any, Dict

ENGINE_NAME = "ROSCOE AI ANIME ENGINE"
ENGINE_VERSION = "0.1.0"

MODEL_PROFILES = {
    "image": {
        "id": "neta-art/Neta-Lumina",
        "name": "Neta Lumina v1.0",
        "task": "anime text-to-image",
        "license": "Apache-2.0",
        "workflow_env": "ROSCOE_IMAGE_WORKFLOW_JSON",
        "minimum_vram_gb": 8,
        "model_url": "https://huggingface.co/neta-art/Neta-Lumina",
        "description": "Anime illustration, character sheets, and scene keyframes."
    },
    "video": {
        "id": "Wan-AI/Wan2.2-TI2V-5B",
        "name": "Wan 2.2 TI2V-5B",
        "task": "text/image-to-video",
        "license": "Apache-2.0",
        "workflow_env": "ROSCOE_VIDEO_WORKFLOW_JSON",
        "model_url": "https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B",
        "minimum_vram_gb": 8,
        "description": "Animates generated keyframes into short video clips."
    }
}


DEFAULT_WORKFLOWS = {
    "image": Path(__file__).resolve().parents[2] / "workflows" / "roscoe_neta_lumina_api.json",
    "video": Path(__file__).resolve().parents[2] / "workflows" / "roscoe_wan22_i2v_api.json",
}

def workflow_path(kind: str) -> str:
    """Use an explicit deployment override or the workflow shipped with FreeVerse."""
    if kind not in MODEL_PROFILES:
        raise ValueError(f"Unknown model stage: {kind}")
    env_name = MODEL_PROFILES[kind]["workflow_env"]
    return os.environ.get(env_name, str(DEFAULT_WORKFLOWS[kind]))

BLOODLINE_BIBLE = {
    "Diamond": "young male warrior, black hair, glowing red eyes",
    "Eternity Infinity": "Diamond's sister; mysterious presence",
    "Murder Co.": "ruthless antagonist emerging from the shadows"
}

NEGATIVE_PROMPT = (
    "low quality, blurry, malformed anatomy, extra fingers, missing fingers, "
    "inconsistent face, inconsistent costume, duplicate characters, fused limbs, "
    "text, watermark, logo, photorealistic, live action, random style changes"
)

def build_scene_prompt(project_title: str, project_description: str,
                       scene_title: str, scene_text: str) -> str:
    """Create a consistent anime keyframe prompt from project and scene context."""
    context = " ".join(x.strip() for x in (
        project_title, project_description, scene_title, scene_text
    ) if x and x.strip())
    character_notes = "; ".join(f"{name}: {description}"
                                for name, description in BLOODLINE_BIBLE.items()
                                if name.lower() in context.lower())
    continuity = (
        "Maintain the same character face, hair, eye color, outfit, proportions, "
        "and art direction across every shot. Cinematic Japanese 2D dark-fantasy anime, "
        "clean expressive linework, detailed cel shading, dramatic composition, "
        "controlled color palette, professional animation keyframe."
    )
    if character_notes:
        continuity += " Character continuity notes: " + character_notes + "."
    return f"{continuity} Series and scene direction: {context}"

def build_motion_prompt(scene_prompt: str, seconds: float = 5.0) -> str:
    return (
        f"{scene_prompt} Animate this as a coherent {seconds:.1f}-second anime shot. "
        "Use continuous natural character and environmental motion, stable identity, "
        "consistent clothing and facial features, intentional camera movement, "
        "no cuts, no morphing, no flicker, no sudden scene changes."
    )

def engine_status(comfyui_reachable: bool, image_workflow_exists: bool,
                  video_workflow_exists: bool) -> Dict[str, Any]:
    return {
        "name": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "models": MODEL_PROFILES,
        "comfyui_reachable": comfyui_reachable,
        "image_workflow_configured": image_workflow_exists,
        "video_workflow_configured": video_workflow_exists,
        "ready": comfyui_reachable and image_workflow_exists and video_workflow_exists,
        "mode": "two_stage_keyframe_then_animation",
        "note": "Model weights and compatible ComfyUI nodes must be installed on the GPU host."
    }
