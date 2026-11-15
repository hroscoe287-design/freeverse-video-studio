import os
import shutil
from pathlib import Path
from typing import Set

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
PROJECTS_DIR = STORAGE_DIR / "projects"
UPLOADS_DIR = STORAGE_DIR / "uploads"
RENDERS_DIR = STORAGE_DIR / "renders"
SAMPLE_ASSETS_DIR = STORAGE_DIR / "sample_assets"

# Ensure all directories exist
for folder in [STORAGE_DIR, PROJECTS_DIR, UPLOADS_DIR, RENDERS_DIR, SAMPLE_ASSETS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Detect FFmpeg executable
def find_ffmpeg_executable() -> str:
    # 1. Check custom env var
    env_path = os.environ.get("FREEVERSE_FFMPEG_PATH") or os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    
    # 2. Check system PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    
    # 3. Check imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    
    # 4. Fallback default
    return "ffmpeg"

FFMPEG_EXE = find_ffmpeg_executable()

# Security & Limits
MAX_UPLOAD_SIZE_BYTES = 150 * 1024 * 1024  # 150 MB max per upload
MAX_RENDER_DURATION_SEC = 600  # 10 minutes max video render time
MAX_RENDER_PROCESS_TIMEOUT_SEC = 300  # 5 min process timeout

ALLOWED_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".webp",
    ".mp4", ".webm", ".mov",
    ".mp3", ".wav", ".ogg", ".aac",
    ".txt", ".md", ".json"
}

ALLOWED_MIME_PREFIXES: Set[str] = {
    "image/", "video/", "audio/", "text/"
}

# Network bindings. Render supplies the public host/port at runtime.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

# Allow local development and Capacitor Android origins. Additional hosted
# frontend origins can be supplied as a comma-separated CORS_ORIGINS env var.
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://localhost",
    "http://localhost",
    "capacitor://localhost",
]
_EXTRA_CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ORIGINS = list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + _EXTRA_CORS_ORIGINS))
