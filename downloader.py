import yt_dlp
import os
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")

def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def download_video(url: str, quality: str = "best") -> dict:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
        # ── Cookie auth ──────────────────────────────────────
        "cookiefile": COOKIES_FILE,
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

        if quality == "audio":
            filepath = filepath.rsplit(".", 1)[0] + ".mp3"

        return {
            "filepath": filepath,
            "title": info.get("title", "video"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "is_short": info.get("duration", 0) <= 60,
        }