"""Roscoe Adaptive Anime Engine (RAAE).

A model-pool-aware generation orchestrator for FreeVerse. It sends inference to
community GPU workers (so the phone does not load model weights), chooses an
available anime-oriented checkpoint, and adapts the sampling budget to the
selected model family. This is orchestration around open models, not a claim
that Roscoe trained a new foundation model.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..config import UPLOADS_DIR
from ..models.render_job import AssetMeta
from .storage import save_asset_meta

API_BASE = os.environ.get("AI_HORDE_BASE_URL", "https://aihorde.net/api").rstrip("/")
ANONYMOUS_KEY = "0000000000"
CLIENT_AGENT = "RoscoesAdaptiveAnimeEngine:2.0:github.com/hroscoe287-design/freeverse-video-studio"
ANIME_HINTS = ("anime", "animagine", "illustrious", "noobai", "pony", "counterfeit", "anything")
NEGATIVE_DEFAULT = (
    "low quality, worst quality, blurry, jpeg artifacts, bad anatomy, bad hands, "
    "extra fingers, missing fingers, fused fingers, malformed limbs, duplicate people, "
    "deformed face, inconsistent character, text, watermark, logo, photorealistic, 3d render"
)


def _request(path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 45) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Client-Agent": CLIENT_AGENT,
        "apikey": os.environ.get("AI_HORDE_API_KEY", ANONYMOUS_KEY),
    }
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data, headers=headers,
        method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _live_models() -> List[Dict[str, Any]]:
    """Return the currently served image models; empty means status is unavailable."""
    try:
        result = _request("/v2/status/models?type=image", timeout=12)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def choose_anime_model(models: List[Dict[str, Any]]) -> Optional[str]:
    """Prefer live anime checkpoints with workers; otherwise allow Horde routing."""
    ranked = []
    for model in models:
        name = str(model.get("name") or "")
        lower = name.lower()
        if not name or not any(hint in lower for hint in ANIME_HINTS):
            continue
        workers = int(model.get("count") or model.get("workers") or 0)
        performance = float(model.get("performance") or 0)
        queued = int(model.get("queued") or 0)
        # Prefer anime-specific checkpoints, then available workers and lower queue.
        specificity = 3 if any(x in lower for x in ("animagine", "illustrious", "noobai")) else 1
        ranked.append((specificity * 100 + min(workers, 30) * 3 + min(performance, 100) - min(queued, 100) * 0.2, name))
    return max(ranked)[1] if ranked else None


def build_anime_prompt(prompt: str, character_bible: str = "", style: str = "cinematic 2D Japanese anime") -> str:
    """Normalize prompts into a compact shot brief; preserve user story facts."""
    clean = re.sub(r"\s+", " ", (prompt or "").strip())
    bible = re.sub(r"\\s+", " ", (character_bible or "").strip())
    parts = [
        "high quality original 2D Japanese anime keyframe",
        style,
        "professional anime film layout, clean confident line art, expressive faces, "
        "cel shading, controlled highlights, detailed painted background, cinematic composition",
    ]
    if bible:
        parts.append("CHARACTER CONTINUITY — preserve these exact designs: " + bible)
    if clean:
        parts.append("SHOT CONTENT — " + clean)
    parts.append("single coherent frame, readable silhouette, intentional camera framing, consistent costume and hair")
    return ", ".join(parts)


def adaptive_params(model_name: Optional[str], width: int = 768, height: int = 512) -> Dict[str, Any]:
    """Use modest image sizes and family-aware step counts to reduce worker compute."""
    name = (model_name or "").lower()
    # SDXL/Illustrious-family checkpoints need more steps than distilled/Lightning models.
    if any(x in name for x in ("lightning", "turbo", "lcm")):
        steps, cfg, sampler = 8, 2.0, "k_euler"
    elif any(x in name for x in ("sdxl", "animagine", "illustrious", "noobai", "pony")):
        steps, cfg, sampler = 24, 6.5, "k_euler_a"
    else:
        steps, cfg, sampler = 20, 6.0, "k_euler_a"
    # Horde requires dimensions to be multiples of 64; clamp to a light but useful canvas.
    width = max(512, min(1024, int(width) // 64 * 64))
    height = max(512, min(768, int(height) // 64 * 64))
    return {
        "n": 1, "width": width, "height": height,
        "steps": steps, "cfg_scale": cfg, "sampler_name": sampler,
        "karras": True, "seed": secrets.randbelow(2**31 - 1),
    }


def provider_status() -> Dict[str, Any]:
    models = _live_models()
    model = choose_anime_model(models)
    return {
        "provider": "AI Horde volunteer GPU network",
        "online": bool(models),
        "anime_model": model,
        "available_image_models": len(models),
        "phone_compute_required": False,
        "mode": "live anime-model routing" if model else "automatic community-worker routing",
    }


def generate_anime_image(
    prompt: str,
    negative_prompt: str = "",
    width: int = 768,
    height: int = 512,
    timeout_seconds: int = 900,
    progress: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, str]:
    """Generate a real image through a remote volunteer worker and save it as an asset."""
    models = _live_models()
    model_name = choose_anime_model(models)
    params = adaptive_params(model_name, width, height)
    full_prompt = build_anime_prompt(prompt)
    negative = negative_prompt.strip() or NEGATIVE_DEFAULT
    request_data: Dict[str, Any] = {
        "prompt": f"{full_prompt} ### {negative}",
        "params": params,
        "nsfw": False,
        "censor_nsfw": True,
        "r2": True,
        "shared": False,
        "slow_workers": False,
    }
    if model_name:
        request_data["models"] = [model_name]

    queued = _request("/v2/generate/async", request_data)
    job_id = queued.get("id")
    if not job_id:
        raise RuntimeError(f"AI Horde rejected the image request: {queued}")
    if progress:
        progress(f"Queued on {model_name or 'the shared anime-capable worker pool'}")

    deadline = time.monotonic() + max(60, int(timeout_seconds))
    while time.monotonic() < deadline:
        time.sleep(4)
        check = _request(f"/v2/generate/check/{job_id}", timeout=20)
        if check.get("faulted"):
            raise RuntimeError("The volunteer worker failed this image. Retry the scene.")
        finished = check.get("finished", 0)
        if check.get("done") or (isinstance(finished, (int, float)) and finished >= 1):
            break
        if progress:
            wait = check.get("wait_time")
            progress(f"Waiting for an AI worker{f' — about {int(wait)}s' if isinstance(wait, (int, float)) else ''}")
    else:
        raise TimeoutError("The image is still waiting in the shared worker queue. Try again later.")

    result = _request(f"/v2/generate/status/{job_id}", timeout=45)
    generations = result.get("generations") or []
    if not generations or not generations[0].get("img"):
        raise RuntimeError("The worker finished but did not return an image.")
    image_url = generations[0]["img"]
    request = urllib.request.Request(image_url, headers={"User-Agent": CLIENT_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        image_bytes = response.read()
        content_type = response.headers.get("Content-Type", "image/png").split(";")[0]
    if not image_bytes:
        raise RuntimeError("The AI worker returned an empty image.")

    suffix = ".webp" if "webp" in content_type else ".jpg" if "jpeg" in content_type else ".png"
    filename = f"roscoe_anime_{secrets.token_hex(12)}{suffix}"
    destination = UPLOADS_DIR / filename
    destination.write_bytes(image_bytes)
    meta = AssetMeta(
        original_filename=f"Roscoe-AI-{job_id}{suffix}",
        stored_filename=filename,
        file_path=str(destination),
        url=f"/api/assets/raw/{filename}",
        mime_type=content_type,
        size_bytes=len(image_bytes),
        media_type="image",
    )
    save_asset_meta(meta)
    return destination, meta.id
