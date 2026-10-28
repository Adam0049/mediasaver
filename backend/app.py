import os, re, time, secrets, tempfile, threading
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import yt_dlp

app = FastAPI(title="MediaSaver API", version="0.1.0")

# Configure these in the hosting provider's environment settings.
API_KEY = os.getenv("MEDIA_SAVER_API_KEY", "")
FRONTEND_ORIGINS = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "").split(",") if x.strip()]
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(500 * 1024 * 1024)))
MAX_DURATION_SECONDS = int(os.getenv("MAX_DURATION_SECONDS", "3600"))

ALLOWED_DOMAINS = {
    "instagram.com", "youtube.com", "youtu.be", "tiktok.com", "facebook.com",
    "fb.watch", "snapchat.com"
}
RATE_LIMIT = 5
RATE_WINDOW = 60
_requests: Dict[str, List[float]] = {}
_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

class DownloadRequest(BaseModel):
    url: HttpUrl


def host_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)


def rate_limit(ip: str):
    now = time.time()
    with _lock:
        values = [t for t in _requests.get(ip, []) if now - t < RATE_WINDOW]
        if len(values) >= RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many requests. Wait a minute and try again.")
        values.append(now)
        _requests[ip] = values


def remove_file(path: str):
    try:
        Path(path).unlink(missing_ok=True)
        Path(path).parent.rmdir()
    except Exception:
        pass

@app.get("/health")
def health():
    return {"status": "ok", "service": "MediaSaver API", "max_file_mb": MAX_FILE_BYTES // (1024 * 1024)}

@app.post("/api/download")
def download_media(payload: DownloadRequest, request: Request, background_tasks: BackgroundTasks, x_api_key: str = Header(default="")):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Backend is not configured. Set MEDIA_SAVER_API_KEY in the hosting dashboard.")
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Missing or incorrect API key. Check MediaSaver settings.")

    url = str(payload.url)
    parsed_host = payload.url.host or ""
    if payload.url.scheme not in ("http", "https") or not host_allowed(parsed_host):
        raise HTTPException(status_code=400, detail="This URL is not from one of the supported platforms.")
    rate_limit(request.client.host if request.client else "unknown")

    workdir = tempfile.mkdtemp(prefix="mediasaver-")
    opts = {
        "outtmpl": str(Path(workdir) / "%(title).150B-%(id)s.%(ext)s"),
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": MAX_FILE_BYTES,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "restrictfilenames": True,
        "overwrites": True,
        "cachedir": False,
        "extractor_args": {"youtube": {"player_client": ["default"]}},
        "match_filter": yt_dlp.utils.match_filter_func(f"duration > {MAX_DURATION_SECONDS}"),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        files = [p for p in Path(workdir).iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl", ".json"))]
        if not files:
            raise RuntimeError("The platform did not return a downloadable media file.")
        file_path = max(files, key=lambda p: p.stat().st_size)
        size = file_path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise RuntimeError("The downloaded file exceeds the configured size limit.")
        filename = re.sub(r"[^A-Za-z0-9._ -]", "_", file_path.name)[:180] or "mediasaver-download.mp4"
        background_tasks.add_task(remove_file, str(file_path))
        return FileResponse(str(file_path), filename=filename, media_type="application/octet-stream", background=background_tasks)
    except HTTPException:
        raise
    except Exception as exc:
        for p in Path(workdir).glob("*"):
            try: p.unlink(missing_ok=True)
            except Exception: pass
        try: Path(workdir).rmdir()
        except Exception: pass
        message = str(exc)
        if "Unsupported URL" in message:
            message = "This link type is not supported by the current downloader."
        elif "Private video" in message or "login" in message.lower() or "sign in" in message.lower():
            message = "This content requires authentication. MediaSaver does not accept passwords or session cookies; use the platform's official download/export options."
        elif "maximum file size" in message.lower() or "max-filesize" in message.lower():
            message = "The media exceeds the configured file-size limit."
        else:
            message = "Download failed. The content may be unavailable, unsupported, or restricted by the platform."
        raise HTTPException(status_code=422, detail=message)
