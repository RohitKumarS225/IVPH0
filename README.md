# IVPH — Image / Video Processing Hub

A local web app that extracts frames (screenshots) from any video — uploaded file or
online link (YouTube, Dailymotion, Vimeo, etc.) — at whatever interval you choose,
down to milliseconds, and packages them into a downloadable ZIP.

---

## 1. What's inside

```
IVPH/
├── app.py                 # Flask backend (upload, URL fetch, ffmpeg extraction, zip)
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # UI
├── static/
│   ├── style.css
│   └── script.js
├── uploads/                 # videos land here (auto-created)
└── outputs/                 # extracted frames + zips land here (auto-created)
```

## 2. Prerequisites

You need three things installed on your machine (Windows / macOS / Linux all work):

1. **Python 3.9+**
2. **ffmpeg** — does the actual frame extraction
   - Windows: `winget install ffmpeg` (or download from ffmpeg.org and add to PATH)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
   - Verify with: `ffmpeg -version`
3. **pip** (comes with Python)

## 3. Setup

```bash
# 1. Unzip/copy the IVPH folder, then move into it
cd IVPH

# 2. (Recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## 4. Run it

```bash
python app.py
```

You'll see Flask start on `http://0.0.0.0:5000`. Open your browser at:

```
http://localhost:5000
```

That's your IVPH web app, running fully on your own machine.

## 5. How to use IVPH

1. **Choose a source**
   - **Upload File** tab → click the drop-zone (or drag a file in) → pick a video
     (.mp4, .mov, .avi, .mkv, .webm, .flv, .wmv, .m4v, .3gp, .vid, etc.) → click **Upload Video**.
   - **Video URL** tab → paste a YouTube / Dailymotion / Vimeo / other public video link →
     click **Fetch Video**. The server downloads it with `yt-dlp`.

2. **Set extraction settings** (appears once your video is loaded)
   - **Capture every** — type a number and choose **Seconds** or **Milliseconds**.
     - e.g. `1` + Seconds → one frame every second
     - e.g. `500` + Milliseconds → one frame every half-second (2 fps)
     - e.g. `40` + Milliseconds → ~25 frames per second (near frame-by-frame)
   - **Image format** — PNG (lossless, bigger files), JPG, or JPEG.
   - Click **Extract Frames**.

3. **Download**
   - Once processing finishes, click **Download ZIP**.
   - You get a `.zip` file (e.g. `IVPH_frames_ab12cd34.zip`) containing every frame as
     `frame_000001.png`, `frame_000002.png`, … in capture order — unzip it to get your
     folder of images.

## 6. Notes & tips

- **Very small intervals** (e.g. every 10ms on a long video) will produce a *lot* of
  frames and take longer — start with 1 second and adjust from there.
- **Large videos / long downloads**: the current version processes requests
  synchronously (progress bar is a visual estimate). For production use on very large
  files, consider adding a task queue (Celery/RQ) and websocket/polling-based real
  progress — the backend already isolates extraction logic in `extract_frames()`
  in `app.py` so it's easy to wrap in a background job later.
- **Storage**: uploaded videos and generated zips are auto-cleaned after ~6 hours
  (see `cleanup_old_files` in `app.py`). Adjust `max_age_seconds` if you want them
  kept longer/shorter.
- **Unsupported URL**: if a link fails to download, it's usually because the site
  isn't supported by `yt-dlp` or the video is private/region-locked. Check the error
  message shown in the app.
- **Max upload size**: capped at 3GB by default (`MAX_CONTENT_LENGTH` in `app.py`) —
  raise it if you need to handle bigger files.

## 7. Quick troubleshooting

| Problem | Fix |
|---|---|
| "ffmpeg was not found" error | Install ffmpeg and confirm `ffmpeg -version` works in your terminal |
| "yt-dlp is not installed" | `pip install yt-dlp` inside your virtual environment |
| Upload fails instantly | Check the file extension is in the allowed list, or increase `MAX_CONTENT_LENGTH` |
| URL fetch fails | Try the direct video page URL (not a playlist/shorts-feed link); some sites block downloads |
| No frames extracted | Your interval may be longer than the video — lower the interval value |

---

Enjoy building with IVPH 🎬
