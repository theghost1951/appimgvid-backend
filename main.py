
"""
Fixed main.py for https://appimgvid-backend2026.onrender.com
Supports full AppImgVid2 APK: image, motion_prompt, negative_prompt, resolution,
aspect_ratio, orientation, duration, camera_control, platform

Drop this into your GitHub repo as main.py, commit, Render will auto-redeploy
"""

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil, os, uuid, json

app = FastAPI(title="AppImgVid2 Backend - Agnes AI")

# Allow your Android APK to call it from any Wi-Fi / mobile network
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # Replace with real auth if you need it - for now allow all
    return {"token": "dummy-token-for-apk", "access_token": "dummy-token-for-apk"}

@app.post("/generate")
async def generate(
    image: UploadFile = File(..., description="Reference image - fully shown"),
    motion_prompt: str = Form(..., description="Full detail repose prompt - body, eyes, smile, hands, feet, elbows, furniture, coffee cup etc"),
    # Optional - these are what your APK wants to send. Making them optional = no 422 error
    prompt: str = Form(None, description="Alias for motion_prompt"),
    negative_prompt: str = Form("", description="Unwanted results prompt"),
    resolution: str = Form("1080", description="640, 720, 1080"),
    aspect_ratio: str = Form("16:9", description="16:9, 9:16, 4:3, 3:4, 1:1, 2:3, 3:2"),
    orientation: str = Form("landscape", description="landscape or portrait"),
    duration: int = Form(8, description="Video length in seconds"),
    duration_seconds: int = Form(None),
    camera_control: str = Form("{}", description='JSON like {"mode":"orbit_360","zoom":1.2}'),
    camera_json: str = Form(None),
    platform: str = Form("agnes")
):
    # Normalize inputs - support both names
    final_prompt = motion_prompt or prompt or ""
    final_duration = duration_seconds if duration_seconds is not None else duration
    final_camera = camera_json if camera_json else camera_control

    # Save uploaded image temporarily
    temp_id = str(uuid.uuid4())
    temp_path = f"/tmp/{temp_id}_{image.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # --- HERE IS WHERE YOU CALL AGNES AI PLATFORM ---
    # Example:
    # from agnes import AgnesClient
    # client = AgnesClient(api_key=os.getenv("AGNES_API_KEY"))
    # video_url = client.image_to_video(
    #     image_path=temp_path,
    #     prompt=final_prompt,
    #     negative_prompt=negative_prompt,
    #     resolution=resolution,
    #     aspect_ratio=aspect_ratio,
    #     orientation=orientation,
    #     duration=final_duration,
    #     camera=final_camera
    # )

    # For testing, return a placeholder - REPLACE THIS WITH REAL AGNES CALL
    # This is what your APK expects: a string URL
    print(f"[GENERATE] id={temp_id} prompt={final_prompt[:200]} resolution={resolution} aspect={aspect_ratio} duration={final_duration} camera={final_camera} negative={negative_prompt}")

    # TODO: Replace with real video URL from Agnes
    # For now, echo back to prove params work
    video_url = f"https://appimgvid-backend2026.onrender.com/videos/{temp_id}.mp4"
    # If you have real generation, set video_url = actual result

    # Save to history
    entry = {
        "id": temp_id,
        "videoUrl": video_url,
        "video_url": video_url,
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

    # Return JUST a string like your current docs show - APK expects string
    # If you prefer JSON, return entry instead
    return JSONResponse(content=video_url)

# For Render: it runs uvicorn main:app --host 0.0.0.0 --port $PORT
