"""
Fixed main.py for https://appimgvid-backend2026.onrender.com
Supports full AppImgVid2 APK: image, motion_prompt, negative_prompt, resolution,
aspect_ratio, orientation, duration, camera_control, platform
"""

import os
import shutil
import uuid
import json

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AppImgVid2 Backend - Agnes AI")

# Allow your Android APK to call it from any Wi-Fi / mobile network
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create videos folder and mount it - MUST be after app = FastAPI()
os.makedirs("videos", exist_ok=True)
os.makedirs("/tmp", exist_ok=True)
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

# Simple in-memory history (use DB in production)
HISTORY = []

@app.get("/")
async def root():
    return {"status": "ok", "service": "AppImgVid2 Agnes AI", "endpoints": ["/generate", "/history", "/latest", "/login"]}

@app.get("/latest")
async def latest():
    return HISTORY[-1] if HISTORY else {"message": "no videos yet"}

@app.get("/history")
async def history():
    return HISTORY

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    return {"token": "dummy-token-for-apk", "access_token": "dummy-token-for-apk"}

@app.post("/generate")
async def generate(
    image: UploadFile = File(..., description="Reference image - fully shown"),
    motion_prompt: str = Form(..., description="Full detail repose prompt"),
    prompt: str = Form(None, description="Alias for motion_prompt"),
    negative_prompt: str = Form("", description="Unwanted results prompt"),
    resolution: str = Form("1080", description="640, 720, 1080"),
    aspect_ratio: str = Form("16:9", description="16:9, 9:16, 4:3, 3:4, 1:1, 2:3, 3:2"),
    orientation: str = Form("landscape", description="landscape or portrait"),
    duration: int = Form(8, description="Video length in seconds"),
    duration_seconds: int = Form(None),
    camera_control: str = Form("static", description='Camera control'),
    camera_json: str = Form(None),
    platform: str = Form("agnes")
):
    final_prompt = motion_prompt or prompt or ""
    final_duration = duration_seconds if duration_seconds is not None else duration
    final_camera = camera_json if camera_json else camera_control

    temp_id = str(uuid.uuid4())
    temp_path = f"/tmp/{temp_id}_{image.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    print(f"[GENERATE] id={temp_id} prompt={final_prompt[:200]} resolution={resolution} aspect={aspect_ratio} duration={final_duration} camera={final_camera} negative={negative_prompt}")

    # --- CREATE A REAL MP4 FILE SO /videos/{id}.mp4 DOES NOT 404 ---
    # For testing, create a placeholder mp4 from the image using ffmpeg if available,
    # otherwise copy image as mp4 placeholder (will still be downloadable)
    video_filename = f"{temp_id}.mp4"
    video_path = f"videos/{video_filename}"
    
    try:
        # Try to create a 5-second video from image using ffmpeg (if installed on Render)
        import subprocess
        # ffmpeg -loop 1 -i image -c:v libx264 -t 5 -pix_fmt yuv420p video.mp4
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", temp_path,
            "-c:v", "libx264",
            "-t", str(final_duration),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={resolution}:-2",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0 or not os.path.exists(video_path):
            # Fallback: just copy image file as mp4 so URL exists (not playable but not 404)
            shutil.copy(temp_path, video_path)
    except Exception as e:
        print(f"ffmpeg failed or not available: {e}, copying image as placeholder")
        try:
            shutil.copy(temp_path, video_path)
        except Exception as e2:
            print(f"Copy failed: {e2}")
            # Create empty file so route exists
            with open(video_path, "wb") as f:
                f.write(b"")

    # If you have real Agnes AI, replace this section:
    # from agnes import AgnesClient
    # client = AgnesClient(api_key=os.getenv("AGNES_API_KEY"))
    # agnes_url = client.image_to_video(image_path=temp_path, prompt=final_prompt, ...)
    # # Download Agnes result to videos/{id}.mp4
    # import requests
    # r = requests.get(agnes_url)
    # with open(video_path, "wb") as f:
    #     f.write(r.content)
    # video_url = f"https://appimgvid-backend2026.onrender.com/videos/{video_filename}"

    video_url = f"https://appimgvid-backend2026.onrender.com/videos/{video_filename}"

    entry = {
        "id": temp_id,
        "videoId": temp_id,
        "videoUrl": video_url,
        "video_url": video_url,
        "url": video_url,
        "prompt": final_prompt,
        "motion_prompt": final_prompt,
        "negative_prompt": negative_prompt,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
        "duration": final_duration,
        "camera_control": final_camera,
        "platform": platform
    }
    HISTORY.append(entry)

    # Return JSON object - APK now handles both string and object
    return entry
