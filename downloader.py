import yt_dlp
import os
import time
import logging
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")


def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def download_video(url: str, quality: str = "best") -> dict:
    """
    Downloads a YouTube video or Short with automatic retry on bot detection.
    quality: "best", "720p", "480p", "audio"
    Returns dict with file path and metadata.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    last_error = None
    for attempt in range(3):
        try:
            return _do_download(url, quality)
        except Exception as e:
            last_error = e
            if "Sign in to confirm" in str(e):
                wait = 5 * (attempt + 1)  # 5s, 10s, 15s
                logging.warning(
                    f"Bot detection hit, retrying in {wait}s "
                    f"(attempt {attempt + 1}/3)..."
                )
                time.sleep(wait)
            else:
                raise  # non-bot errors fail immediately

    raise last_error


def _do_download(url: str, quality: str) -> dict:
    # Debug: confirm cookie file exists
    if os.path.exists(COOKIES_FILE):
        logging.info(f"✅ Cookie file found: {COOKIES_FILE} ({os.path.getsize(COOKIES_FILE)} bytes)")
    else:
        logging.error(f"❌ Cookie file NOT found at: {COOKIES_FILE}")

    format_map = {
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/mp4/best",
        "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/mp4",
        "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]/mp4",
        "audio": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
    }

    ydl_opts = {
        "format": format_map.get(quality, format_map["best"]),
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
        "cookiefile": COOKIES_FILE,
        "format_sort": ["res", "ext:mp4:m4a"],
        "sleep_interval": 3,
        "max_sleep_interval": 6,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if quality == "audio":
        ydl_opts["format"] = format_map["audio"]
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)

        # Handle audio extension swap
        if quality == "audio":
            filepath = filepath.rsplit(".", 1)[0] + ".mp3"

        return {
            "filepath": filepath,
            "title": info.get("title", "video"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "is_short": info.get("duration", 0) <= 60,
        }