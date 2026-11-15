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


@router.get("/capabilities")
def generator_capabilities():
    """Report actual storyboard, render, and ComfyUI workflow availability."""
    endpoint = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    configured = bool(os.environ.get("COMFYUI_BASE_URL"))
    workflow_path = os.environ.get("COMFYUI_WORKFLOW_JSON", "")
    workflow_exists = bool(workflow_path and Path(workflow_path).expanduser().is_file())
    reachable = False
    detail = "No ComfyUI server configured. Storyboards and FFmpeg editing are available; AI scene generation is not."
    try:
        headers = {"User-Agent": "FreeVerseStudio"}
        api_key = os.environ.get("COMFYUI_API_KEY")
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        req = urllib.request.Request(f"{endpoint}/system_stats", headers=headers)
        with urllib.request.urlopen(req, timeout=2.5) as response:
            reachable = response.status == 200
    except Exception:
        if configured:
            detail = "COMFYUI_BASE_URL is set, but the generation server could not be reached from this backend."
    ready = reachable and workflow_exists
    if reachable and not workflow_exists:
        detail = "ComfyUI is connected. Set COMFYUI_WORKFLOW_JSON to an API-format workflow file to enable scene generation."
    elif ready:
        detail = "ComfyUI and a workflow file are configured. Generation will work if the workflow's models and nodes are installed."
    return {
        "storyboard": True,
        "ffmpeg_render": True,
        "comfyui_configured": configured,
        "comfyui_reachable": reachable,
        "workflow_configured": bool(workflow_path),
        "workflow_file_exists": workflow_exists,
        "anime_generation_ready": ready,
        "detail": detail
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
            prompt = (
                "Create a polished cinematic Japanese dark fantasy anime sequence, "
                "consistent premium 2D anime art direction, detailed expressive characters, "
                "coherent anatomy, dramatic film lighting, dynamic composition. "
                "Series: BLOODLINE. Character continuity: Diamond is a young male warrior "
                "with black hair and glowing red eyes; Eternity Infinity is his mysterious "
                "sister; Murder Co. is the ruthless antagonist. Preserve established designs. "
                f"Scene direction: {scene_text}. "
                "If the workflow supports video output, animate clear continuous motion, "
                "not a slideshow or static title card."
            )
            negative = (
                "low quality, blurry, malformed anatomy, extra fingers, inconsistent costume, "
                "duplicate characters, text, watermark, logo, photorealistic, live action"
            )
            media_path, asset_id = generate_scene_media(prompt, negative)
            scene.asset_id = asset_id
            scene.motion_effect = "none" if media_path.suffix.lower() in {".mp4", ".webm", ".mov", ".gif"} else "ken_burns_zoom_in"
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
    if not os.environ.get("COMFYUI_WORKFLOW_JSON"):
        raise HTTPException(
            status_code=503,
            detail="The anime engine is not configured yet. Connect ComfyUI and set COMFYUI_WORKFLOW_JSON to an API-format text-to-video or image-to-video workflow."
        )
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
