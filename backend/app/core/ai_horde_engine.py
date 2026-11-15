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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from ..config import UPLOADS_DIR
from ..models.render_job import AssetMeta
from .storage import save_asset_meta

API_BASE = os.environ.get("AI_HORDE_BASE_URL", "https://aihorde.net/api").rstrip("/")
ANONYMOUS_KEY = "0000000000"
CLIENT_AGENT = "RoscoesAdaptiveAnimeEngine:2.1:github.com/hroscoe287-design/freeverse-video-studio"
ANIME_HINTS = ("anime", "animagine", "illustrious", "noobai", "pony", "counterfeit", "anything")
NEGATIVE_DEFAULT = (
    "low quality, worst quality, blurry, jpeg artifacts, bad anatomy, bad hands, "
    "extra fingers, missing fingers, fused fingers, malformed limbs, duplicate people, "
    "deformed face, inconsistent character, text, watermark, logo, photorealistic, 3d render"
)


def _headers() -> Dict[str, str]:
    # An explicitly present but empty Render variable must not suppress anonymous access.
    api_key = (os.environ.get("AI_HORDE_API_KEY") or "").strip() or ANONYMOUS_KEY
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Client-Agent": CLIENT_AGENT,
        "apikey": api_key,
        # Cloudflare can reject urllib's default Python client fingerprint.
        "User-Agent": "RoscoesAdaptiveAnimeEngine/2.1 (FreeVerse Video Studio)",
    }


def _request(path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 45) -> Dict[str, Any]:
    """Call AI Horde with requests; urllib is blocked by Cloudflare on some routes."""
    url = f"{API_BASE}{path}"
    try:
        response = requests.post(url, json=payload, headers=_headers(), timeout=timeout) if payload is not None else requests.get(url, headers=_headers(), timeout=timeout)
        response.raise_for_status()
        if not response.content:
            return {}
        result = response.json()
        if not isinstance(result, dict) and not isinstance(result, list):
            raise RuntimeError("AI Horde returned an unexpected response format.")
        return result
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        detail = ""
        if exc.response is not None:
            detail = (exc.response.text or "")[:400]
        if status == 403:
            raise RuntimeError(
                "AI Horde denied the request (HTTP 403). Check the AI_HORDE_API_KEY "
                "Render variable or retry if Cloudflare is temporarily blocking the host. "
                f"Provider response: {detail}"
            ) from exc
        raise RuntimeError(f"AI Horde HTTP {status}: {detail or str(exc)}") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach AI Horde: {exc}") from exc


def _live_models() -> List[Dict[str, Any]]:
    """Return the currently served image models; empty means status is unavailable."""
    try:
        result = _request("/v2/status/models", timeout=12)
        return [m for m in result if isinstance(m, dict) and m.get("type", "image") == "image"] if isinstance(result, list) else []
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
        specificity = 3 if any(x in lower for x in ("animagine", "illustrious", "noobai")) else 1
        ranked.append((specificity * 100 + min(workers, 30) * 3 + min(performance, 100) - min(queued, 100) * 0.2, name))
    return max(ranked)[1] if ranked else None


def build_anime_prompt(prompt: str, character_bible: str = "", style: str = "cinematic 2D Japanese anime") -> str:
    """Normalize prompts into a compact shot brief; preserve user story facts."""
    clean = re.sub(r"\s+", " ", (prompt or "").strip())
    bible = re.sub(r"\s+", " ", (character_bible or "").strip())
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


def adaptive_params(model_name: Optional[str], width: int = 512, height: int = 512) -> Dict[str, Any]:
    """Use modest image sizes and family-aware step counts to reduce worker compute."""
    name = (model_name or "").lower()
    anonymous = not (os.environ.get("AI_HORDE_API_KEY") or "").strip()
    if anonymous:
        # Minimal first-order-equivalent workload for the public no-key tier.
        # Keep frames small; the editor can scale them for the video timeline.
        steps, cfg, sampler = 4, 2.0, "k_euler"
        width = height = 256
    else:
        if any(x in name for x in ("lightning", "turbo", "lcm")):
            steps, cfg, sampler = 6, 2.0, "k_euler"
        elif any(x in name for x in ("sdxl", "animagine", "illustrious", "noobai", "pony")):
            steps, cfg, sampler = 12, 5.5, "k_euler_a"
        else:
            steps, cfg, sampler = 12, 5.0, "k_euler_a"
        width = min(768, max(512, int(width) // 64 * 64))
        height = min(768, max(512, int(height) // 64 * 64))
    return {
        "n": 1, "width": width, "height": height,
        "steps": steps, "cfg_scale": cfg, "sampler_name": sampler,
        "karras": not anonymous, "seed": str(secrets.randbelow(2**31 - 1)),
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
    width: int = 512,
    height: int = 512,
    timeout_seconds: int = 900,
    progress: Optional[Callable[[str], None]] = None,
) -> Tuple[Path, str]:
    """Generate a real image through a remote volunteer worker and save it as an asset."""
    models = _live_models()
    anonymous = not (os.environ.get("AI_HORDE_API_KEY") or "").strip()
    # Do not pin anonymous jobs to a high-cost SDXL checkpoint; let Horde route
    # them to any compatible volunteer worker.
    model_name = None if anonymous else choose_anime_model(models)
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
    parsed_url = urlparse(image_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise RuntimeError("AI Horde returned an invalid image URL.")
    try:
        image_response = requests.get(image_url, headers={"User-Agent": _headers()["User-Agent"]}, timeout=120)
        image_response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not download the generated anime image: {exc}") from exc
    image_bytes = image_response.content
    content_type = image_response.headers.get("Content-Type", "image/png").split(";")[0]
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
