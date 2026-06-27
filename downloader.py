import yt_dlp
import os
from config import DOWNLOAD_DIR, MAX_FILE_SIZE_MB

def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

def download_video(url: str, quality: str = "best") -> dict:
    """
    Downloads a YouTube video or Short.
    quality: "best", "720p", "480p", "audio"
    Returns dict with file path and metadata.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    format_map = {
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
        "480p":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]",
        "audio": "bestaudio[ext=m4a]/bestaudio",
    }

    ydl_opts = {
        # "format": format_map.get(quality, format_map["best"]),
         "format": "best[ext=mp4]/best",
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    if quality == "audio":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }]
        ydl_opts["outtmpl"] = f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"

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