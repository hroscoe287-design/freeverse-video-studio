"""ComfyUI API workflow runner for real generated scene media.

Configure COMFYUI_BASE_URL and COMFYUI_WORKFLOW_JSON on the backend.
The workflow must be ComfyUI's API-format JSON and contain these text tokens:
__PROMPT__, __NEGATIVE_PROMPT__, and optionally __SEED__.
The workflow should end in a video output node (preferred) or SaveImage node.
"""
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

from ..config import UPLOADS_DIR
from ..models.render_job import AssetMeta
from .storage import save_asset_meta

def _request_json(url: str, payload: Dict[str, Any] = None, timeout: int = 30) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "FreeVerseStudio"}
    api_key = os.environ.get("COMFYUI_API_KEY")
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(
        url, data=data, headers=headers,
        method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def _replace_tokens(value: Any, prompt: str, negative: str, seed: int) -> Any:
    if isinstance(value, dict):
        return {k: _replace_tokens(v, prompt, negative, seed) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_tokens(v, prompt, negative, seed) for v in value]
    if isinstance(value, str):
        return (value.replace("__PROMPT__", prompt)
                     .replace("__NEGATIVE_PROMPT__", negative)
                     .replace("__SEED__", str(seed)))
    return value

def generate_scene_media(prompt: str, negative_prompt: str = "") -> Tuple[Path, str]:
    base = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    workflow_path = os.environ.get("COMFYUI_WORKFLOW_JSON")
    if not workflow_path:
        raise RuntimeError("Anime workflow is not configured. Set COMFYUI_WORKFLOW_JSON to a ComfyUI API-format workflow file.")
    path = Path(workflow_path).expanduser()
    if not path.is_file():
        raise RuntimeError(f"ComfyUI workflow file not found: {path}")
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Could not read ComfyUI workflow JSON: {exc}") from exc
    if not isinstance(workflow, dict) or not workflow:
        raise RuntimeError("ComfyUI workflow must be a non-empty API-format JSON object.")

    seed = secrets.randbelow(2**31 - 1)
    workflow = _replace_tokens(workflow, prompt, negative_prompt, seed)
    queued = _request_json(f"{base}/prompt", {"prompt": workflow}, timeout=45)
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not queue the workflow: {queued}")

    deadline = time.monotonic() + int(os.environ.get("COMFYUI_TIMEOUT_SECONDS", "900"))
    history: Dict[str, Any] = {}
    while time.monotonic() < deadline:
        time.sleep(2)
        result = _request_json(f"{base}/history/{urllib.parse.quote(str(prompt_id))}", timeout=30)
        history = result.get(str(prompt_id), result)
        if history.get("outputs"):
            break
        if history.get("status", {}).get("status_str") == "error":
            raise RuntimeError("ComfyUI workflow failed. Check the ComfyUI console for the node error.")
    else:
        raise TimeoutError("ComfyUI generation timed out. Try fewer frames or a lighter workflow.")

    outputs = history.get("outputs", {})
    selected = None
    media_kind = None
    for key in ("videos", "gifs", "images"):
        for node in outputs.values():
            if not isinstance(node, dict):
                continue
            items = node.get(key)
            if items:
                selected, media_kind = items[0], key
                break
        if selected:
            break
    if not selected or not selected.get("filename"):
        raise RuntimeError("ComfyUI finished but the workflow returned no video, GIF, or image output.")

    filename = str(selected["filename"])
    subfolder = str(selected.get("subfolder", ""))
    output_type = str(selected.get("type", "output"))
    query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": output_type})
    view_headers = {"User-Agent": "FreeVerseStudio"}
    api_key = os.environ.get("COMFYUI_API_KEY")
    if api_key:
        view_headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(f"{base}/view?{query}", headers=view_headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "")
    if not data:
        raise RuntimeError("ComfyUI returned an empty media file.")

    suffix = Path(filename).suffix.lower()
    if not suffix:
        suffix = ".mp4" if media_kind in ("videos", "gifs") else ".png"
    if suffix not in {".mp4", ".webm", ".mov", ".gif", ".png", ".jpg", ".jpeg", ".webp"}:
        raise RuntimeError(f"Unsupported ComfyUI output format: {suffix}")
    stored = f"anime_{secrets.token_hex(12)}{suffix}"
    destination = UPLOADS_DIR / stored
    destination.write_bytes(data)
    media_type = "video" if suffix in {".mp4", ".webm", ".mov", ".gif"} else "image"
    meta = AssetMeta(
        original_filename=filename,
        stored_filename=stored,
        file_path=str(destination),
        url=f"/api/assets/raw/{stored}",
        mime_type=content_type or ("video/mp4" if media_type == "video" else "image/png"),
        size_bytes=len(data),
        media_type=media_type
    )
    save_asset_meta(meta)
    return destination, meta.id
