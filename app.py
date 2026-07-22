"""
IVPH - Image/frame extraction from Videos
Flask backend

Handles:
  - Video file uploads (.mp4, .mov, .avi, .mkv, .webm, .flv, .wmv, .m4v, .3gp, .vid ...)
  - Video URLs (YouTube, Dailymotion, Vimeo, and anything yt-dlp supports)
  - Frame extraction at a user-defined interval (seconds OR milliseconds)
  - Output as .png / .jpg / .jpeg
  - Packaging extracted frames into a downloadable .zip
"""

import os
import uuid
import zipfile
import subprocess
import shutil
import time

from flask import Flask, request, jsonify, send_file, render_template

# --------------------------------------------------------------------------
# Paths / config
# --------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4", "mov", "avi", "mkv", "webm", "flv",
    "wmv", "m4v", "3gp", "mpeg", "mpg", "vid", "ts"
}
ALLOWED_IMAGE_FORMATS = {"png", "jpg", "jpeg"}

MAX_CONTENT_LENGTH = 3 * 1024 * 1024 * 1024  # 3 GB upload cap

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def allowed_video_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def find_video_path(video_id: str):
    """Locate a previously uploaded/downloaded video by its id, regardless of extension."""
    for f in os.listdir(UPLOAD_DIR):
        if f.startswith(video_id):
            return os.path.join(UPLOAD_DIR, f)
    return None


def cleanup_old_files(directory: str, max_age_seconds: int = 6 * 3600):
    """Best-effort cleanup of files older than max_age_seconds. Ignored on failure."""
    try:
        now = time.time()
        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            try:
                if now - os.path.getmtime(path) > max_age_seconds:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


# --------------------------------------------------------------------------
# Routes - pages
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------
# Routes - API
# --------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def upload_video():
    """Accepts a multipart file upload and stores it under a generated video_id."""
    if "video" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_video_file(file.filename):
        return jsonify({
            "error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
        }), 400

    video_id = str(uuid.uuid4())
    ext = file.filename.rsplit(".", 1)[1].lower()
    save_path = os.path.join(UPLOAD_DIR, f"{video_id}.{ext}")
    file.save(save_path)

    cleanup_old_files(UPLOAD_DIR)
    cleanup_old_files(OUTPUT_DIR)

    return jsonify({
        "video_id": video_id,
        "filename": file.filename,
        "size_bytes": os.path.getsize(save_path)
    })


@app.route("/api/fetch-url", methods=["POST"])
def fetch_url():
    """Downloads a video from a URL (YouTube, Dailymotion, Vimeo, etc.) using yt-dlp."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        import yt_dlp
    except ImportError:
        return jsonify({
            "error": "yt-dlp is not installed on the server. Run: pip install yt-dlp"
        }), 500

    video_id = str(uuid.uuid4())
    output_template = os.path.join(UPLOAD_DIR, f"{video_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": output_template,
        "format": "bv*[ext=mp4]+ba[ext=m4a]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(info)
            # merge_output_format may change the extension to mp4
            if not os.path.exists(downloaded_path):
                candidate = os.path.join(UPLOAD_DIR, f"{video_id}.mp4")
                if os.path.exists(candidate):
                    downloaded_path = candidate
    except Exception as e:
        return jsonify({"error": f"Failed to download video: {str(e)}"}), 500

    cleanup_old_files(UPLOAD_DIR)
    cleanup_old_files(OUTPUT_DIR)

    return jsonify({
        "video_id": video_id,
        "filename": info.get("title", "video"),
        "duration": info.get("duration"),
        "source": info.get("extractor", "url")
    })


@app.route("/api/extract", methods=["POST"])
def extract_frames():
    """
    Extracts frames from a previously uploaded/downloaded video using ffmpeg,
    at the interval and format requested, then zips the results.
    """
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    interval_value = data.get("interval_value", 1)
    interval_unit = data.get("interval_unit", "seconds")  # "seconds" | "milliseconds"
    img_format = str(data.get("format", "png")).lower()

    if img_format not in ALLOWED_IMAGE_FORMATS:
        return jsonify({"error": f"Unsupported image format '{img_format}'"}), 400

    try:
        interval_value = float(interval_value)
    except (TypeError, ValueError):
        return jsonify({"error": "Interval value must be a number"}), 400

    if interval_value <= 0:
        return jsonify({"error": "Interval value must be greater than 0"}), 400

    video_path = find_video_path(video_id) if video_id else None
    if not video_path or not os.path.exists(video_path):
        return jsonify({"error": "Video not found. Upload or fetch it first."}), 404

    # Convert interval to seconds for ffmpeg's fps filter
    if interval_unit == "milliseconds":
        interval_seconds = interval_value / 1000.0
    else:
        interval_seconds = interval_value

    fps = 1.0 / interval_seconds  # frames per second to capture

    job_id = str(uuid.uuid4())
    frames_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(frames_dir, exist_ok=True)

    out_ext = "jpg" if img_format == "jpeg" else img_format
    output_pattern = os.path.join(frames_dir, f"frame_%06d.{out_ext}")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        output_pattern,
        "-hide_banner", "-loglevel", "error",
    ]

    try:
        subprocess.run(cmd, check=True, timeout=3600)
    except FileNotFoundError:
        return jsonify({
            "error": "ffmpeg was not found on this system. Install it and make sure it's on PATH."
        }), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"ffmpeg failed: {e}"}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Extraction timed out (over 1 hour). Try a larger interval."}), 500

    frame_files = sorted(os.listdir(frames_dir))
    if not frame_files:
        shutil.rmtree(frames_dir, ignore_errors=True)
        return jsonify({"error": "No frames were extracted. Try a larger interval or check the video."}), 500

    zip_path = os.path.join(OUTPUT_DIR, f"{job_id}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in frame_files:
            zf.write(os.path.join(frames_dir, fname), arcname=fname)

    return jsonify({
        "job_id": job_id,
        "frame_count": len(frame_files),
        "format": out_ext,
        "download_url": f"/api/download/{job_id}"
    })


@app.route("/api/download/<job_id>", methods=["GET"])
def download_zip(job_id):
    """Serves the zipped frames folder for download."""
    # basic sanitization - job_id must look like a uuid
    if not all(c.isalnum() or c == "-" for c in job_id):
        return jsonify({"error": "Invalid job id"}), 400

    zip_path = os.path.join(OUTPUT_DIR, f"{job_id}.zip")
    if not os.path.exists(zip_path):
        return jsonify({"error": "File not found or has expired"}), 404

    return send_file(
        zip_path,
        as_attachment=True,
        download_name=f"IVPH_frames_{job_id[:8]}.zip"
    )


@app.route("/api/health", methods=["GET"])
def health():
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    return jsonify({"status": "ok", "ffmpeg_available": ffmpeg_ok})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
