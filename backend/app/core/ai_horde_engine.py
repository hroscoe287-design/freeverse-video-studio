"""Free, community-powered anime image generation for Roscoe's Anime Engine.

Uses AI Horde volunteer workers (anonymous key by default). The engine stores
real generated images as project assets; FreeVerse's existing FFmpeg renderer
turns those keyframes into playable MP4 scenes with camera motion.
"""
import json
import os
import secrets
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

from ..config import UPLOADS_DIR
from ..models.render_job import AssetMeta
from .storage import save_asset_meta

API_BASE = os.environ.get("AI_HORDE_BASE_URL", "https://aihorde.net/api").rstrip("/")
ANONYMOUS_KEY = "0000000000"
CLIENT_AGENT = "RoscoesFreeVerseAnime:1.0:github.com/hroscoe287-design/freeverse-video-studio"


def _request(path: str, payload: Dict[str, Any] = None, timeout: int = 45) -> Dict[str, Any]:
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
        return json.loads(response.read().decode("utf-8"))


def generate_anime_image(prompt: str, negative_prompt: str = "",
                         width: int = 768, height: int = 512,
                         timeout_seconds: int = 540) -> Tuple[Path, str]:
    """Request one actual AI-generated anime image and save it as a FreeVerse asset."""
    full_prompt = f"{prompt} ### {negative_prompt}" if negative_prompt else prompt
    request_data = {
        "prompt": full_prompt,
        "params": {
            "n": 1,
            "width": width,
            "height": height,
            "steps": 24,
            "cfg_scale": 7,
            "seed": secrets.randbelow(2**31 - 1),
        },
        "nsfw": False,
        "censor_nsfw": True,
        "r2": True,
        "shared": False,
    }
    queued = _request("/v2/generate/async", request_data)
    job_id = queued.get("id")
    if not job_id:
        raise RuntimeError(f"AI Horde did not accept the image request: {queued}")

    deadline = time.monotonic() + max(60, int(timeout_seconds))
    while time.monotonic() < deadline:
        time.sleep(5)
        check = _request(f"/v2/generate/check/{job_id}")
        if check.get("faulted"):
            raise RuntimeError("AI Horde generation failed. Try again or change the scene prompt.")
        if check.get("done"):
            break
    else:
        raise TimeoutError("AI image generation is still queued. Try again later; anonymous requests have the lowest queue priority.")

    result = _request(f"/v2/generate/status/{job_id}")
    generations = result.get("generations") or []
    if not generations or not generations[0].get("img"):
        raise RuntimeError(f"AI Horde completed without returning an image: {result}")

    image_url = generations[0]["img"]
    headers = {"User-Agent": CLIENT_AGENT}
    request = urllib.request.Request(image_url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        image_bytes = response.read()
        content_type = response.headers.get("Content-Type", "image/png")
    if not image_bytes:
        raise RuntimeError("AI Horde returned an empty image.")

    suffix = ".webp" if "webp" in content_type else ".jpg" if "jpeg" in content_type else ".png"
    filename = f"roscoe_horde_{secrets.token_hex(12)}{suffix}"
    destination = UPLOADS_DIR / filename
    destination.write_bytes(image_bytes)
    meta = AssetMeta(
        original_filename=f"AI-Horde-{job_id}{suffix}",
        stored_filename=filename,
        file_path=str(destination),
        url=f"/api/assets/raw/{filename}",
        mime_type=content_type,
        size_bytes=len(image_bytes),
        media_type="image",
    )
    save_asset_meta(meta)
    return destination, meta.id
