from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import os
import urllib.request
import threading
import time
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from ..models.render_job import PromptGenerateRequest
from ..models.project import Project
from ..core.procedural_gen import generate_storyboard_from_prompt
from ..core.storage import save_project, load_project, get_asset_meta
from ..core.comfyui_pipeline import generate_scene_media
from ..core.ai_horde_engine import generate_anime_image
from ..core.roscoe_anime_engine import (MODEL_PROFILES, NEGATIVE_PROMPT, build_scene_prompt, build_motion_prompt, engine_status, workflow_path)

router = APIRouter(prefix="/api/generator", tags=["generator"])

@router.post("/storyboard", response_model=Project)
def generate_project_storyboard(req: PromptGenerateRequest):
    """
    Creates a full multi-scene project from a natural language prompt,
    customized for the selected video style (Kids, Educational, Social, Natural, AI).
    """
    try:
        project = generate_storyboard_from_prompt(req)
        saved = save_project(project)
        return saved
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate storyboard: {str(e)}")

@router.post("/document-storyboard", response_model=Project)
async def generate_from_document(
    file: UploadFile = File(...),
    style: str = Form("educational"),
    target_duration: float = Form(30.0)
):
    """
    Parses an uploaded text or markdown document to create an educational explainer video.
    """
    content = await file.read()
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot decode text document")

    # Generate prompt from first few sentences or filename
    title = file.filename or "Document Explainer"
    prompt_text = f"Explainer video based on {title}"

    req = PromptGenerateRequest(
        prompt=prompt_text,
        style=style if style in ["educational", "cartoon", "social", "natural", "ai_generated", "visualizer"] else "educational",
        target_duration=target_duration,
        scene_count=5,
        include_voiceover=True,
        source_document=text[:4000]
    )

    project = generate_storyboard_from_prompt(req)
    saved = save_project(project)
    return saved


@router.get("/engine")
def roscoe_anime_engine_status():
    """Describe the selected open-weight models and the configured generation runtime."""
    endpoint = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    reachable = False
    try:
        headers = {"User-Agent": "RoscoeAnimeEngine"}
        api_key = os.environ.get("COMFYUI_API_KEY")
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        req = urllib.request.Request(f"{endpoint}/system_stats", headers=headers)
        with urllib.request.urlopen(req, timeout=2.5) as response:
            reachable = response.status == 200
    except Exception:
        pass
    image_path = workflow_path("image")
    video_path = workflow_path("video")
    return engine_status(
        reachable,
        bool(image_path and Path(image_path).expanduser().is_file()),
        bool(video_path and Path(video_path).expanduser().is_file())
    )

@router.get("/capabilities")
def generator_capabilities():
    """Expose truthful readiness for the two-stage Roscoe Anime Engine."""
    engine = roscoe_anime_engine_status()
    legacy_path = os.environ.get("COMFYUI_WORKFLOW_JSON", "")
    legacy_exists = bool(legacy_path and Path(legacy_path).expanduser().is_file())
    ready = bool(engine["ready"] or legacy_exists)
    if engine["ready"]:
        detail = "Roscoe Anime Engine is ready: anime keyframes and video animation workflows are configured."
    elif not engine["comfyui_reachable"]:
        detail = "GPU generation server is not reachable. Storyboards and editing work; AI media generation is offline."
    elif not engine["image_workflow_configured"]:
        detail = "GPU server is connected. Configure ROSCOE_IMAGE_WORKFLOW_JSON for the anime image model."
    elif not engine["video_workflow_configured"]:
        detail = "Anime image workflow is configured. Configure ROSCOE_VIDEO_WORKFLOW_JSON for character animation."
    else:
        detail = "Generation engine configuration is incomplete."
    return {
        "storyboard": True,
        "ffmpeg_render": True,
        "comfyui_configured": bool(os.environ.get("COMFYUI_BASE_URL")),
        "comfyui_reachable": engine["comfyui_reachable"],
        "workflow_configured": bool(engine["image_workflow_configured"] and engine["video_workflow_configured"]) or legacy_exists,
        "workflow_file_exists": bool(engine["image_workflow_configured"] and engine["video_workflow_configured"]) or legacy_exists,
        "anime_generation_ready": True,
        "generation_provider": "AI Horde free volunteer workers (anonymous queue)",
        "video_mode": "Wan 2.2 image-to-video when ComfyUI is configured; otherwise generated anime keyframes are animated by the existing FFmpeg renderer",
        "engine": engine,
        "detail": (detail if engine["ready"] else "Free anime image generation is enabled through AI Horde volunteer workers. Anonymous requests may wait in a shared queue; generated stills become MP4 scenes through FreeVerse's existing renderer.")
    }

ANIME_JOBS: Dict[str, Dict[str, Any]] = {}
ANIME_JOBS_LOCK = threading.Lock()

def _run_anime_job(job_id: str, project_id: str):
    with ANIME_JOBS_LOCK:
        job = ANIME_JOBS[job_id]
        job["status"] = "running"
        job["message"] = "Connecting to ComfyUI..."
    try:
        project = load_project(project_id)
        if not project or not project.scenes:
            raise RuntimeError("Project not found or has no scenes.")
        total = len(project.scenes)
        for index, scene in enumerate(project.scenes):
            with ANIME_JOBS_LOCK:
                job["progress"] = round(index / total * 100, 1)
                job["message"] = f"Generating scene {index + 1} of {total}: {scene.title}"
            scene_text = " ".join(part for part in [
                project.title, project.description, scene.title,
                scene.voiceover_text or "", scene.text_overlay or ""
            ] if part)
            prompt = build_scene_prompt(project.title, project.description, scene.title, scene_text)
            negative = NEGATIVE_PROMPT
            image_workflow = workflow_path("image")
            video_workflow = workflow_path("video")
            if image_workflow and video_workflow:
                keyframe_path, _ = generate_scene_media(
                    prompt, negative, workflow_path=image_workflow, output_preference="image"
                )
                motion_prompt = build_motion_prompt(prompt, min(float(scene.duration), 8.0))
                media_path, asset_id = generate_scene_media(
                    motion_prompt, negative, workflow_path=video_workflow,
                    input_image=keyframe_path, output_preference="video"
                )
            else:
                # Free fallback: request a real anime keyframe from AI Horde.
                # FreeVerse's existing FFmpeg renderer animates the still with camera motion.
                media_path, asset_id = generate_anime_image(prompt, negative)
            scene.asset_id = asset_id
            scene.motion_effect = "none" if media_path.suffix.lower() in {".mp4", ".webm", ".mov", ".gif"} else "ken_burns_zoom_in"
            save_project(project)
            with ANIME_JOBS_LOCK:
                job["progress"] = round((index + 1) / total * 100, 1)
        save_project(project)
        with ANIME_JOBS_LOCK:
            job["status"] = "completed"
            job["progress"] = 100
            job["message"] = "Generated media attached to every scene. Ready to render the MP4."
            job["project_id"] = project_id
    except Exception as exc:
        with ANIME_JOBS_LOCK:
            job["status"] = "failed"
            job["error"] = str(exc)
            job["message"] = "Anime generation failed."

@router.post("/anime/start/{project_id}")
def start_anime_generation(project_id: str):
    image_workflow = workflow_path("image")
    video_workflow = workflow_path("video")
    legacy_workflow = os.environ.get("COMFYUI_WORKFLOW_JSON", "")
    two_stage_ready = (
        image_workflow and Path(image_workflow).expanduser().is_file()
        and video_workflow and Path(video_workflow).expanduser().is_file()
    )
    legacy_ready = legacy_workflow and Path(legacy_workflow).expanduser().is_file()
    # If no private ComfyUI GPU host is configured, use the free AI Horde
    # volunteer-worker image provider and the existing FFmpeg scene animator.
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if not project.scenes:
        raise HTTPException(status_code=400, detail="The project has no scenes to generate.")
    job_id = str(uuid.uuid4())
    with ANIME_JOBS_LOCK:
        ANIME_JOBS[job_id] = {
            "job_id": job_id, "project_id": project_id, "status": "queued",
            "progress": 0, "message": "Queued anime generation", "error": None
        }
    thread = threading.Thread(target=_run_anime_job, args=(job_id, project_id), daemon=True)
    thread.start()
    return ANIME_JOBS[job_id]

@router.get("/anime/status/{job_id}")
def anime_generation_status(job_id: str):
    with ANIME_JOBS_LOCK:
        job = ANIME_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Anime generation job not found.")
        return dict(job)
