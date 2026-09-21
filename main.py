"""
FREE Wan 2.1 Backend for AppImgVid - 100% FREE with Hugging Face API Key
Wan 2.1 FREE backend - Much more cinematic & realistic

Deploy this as main.py on Render
Set HF_API_KEY in Render Env Vars (hf_xxx)

Model: Wan-AI/Wan2.1-I2V-14B-720P - Best open-source image-to-video 2025
Apache 2.0 license, free forever
"""

import os
import shutil
import uuid
import time
import traceback

from fastapi import FastAPI, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AppImgVid Backend - Wan 2.1 FREE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="videos"), name="videos")

HISTORY = []

# ===== PUT YOUR HF KEY HERE OR IN RENDER ENV =====
HARDCODED_HF_KEY = "PASTE_YOUR_HF_KEY_HERE"  # hf_xxx...
# =================================================

HF_MODEL = "Wan-AI/Wan2.1-I2V-14B-720P"  # 720P cinematic
HF_MODEL_FAST = "Wan-AI/Wan2.1-I2V-14B-480P"

def get_hf_key(header_key: str = ""):
    return header_key or os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or HARDCODED_HF_KEY or ""

@app.get("/")
async def root():
    has_key = bool(get_hf_key())
    return {
        "status": "ok", 
        "service": "AppImgVid Wan2.1 FREE", 
        "model": HF_MODEL,
        "endpoints": ["/generate", "/status/{id}", "/history", "/latest"],
        "hf_key_set": has_key,
        "free": True,
        "cinematic": True
    }

@app.get("/latest")
async def latest():
    return HISTORY[-1] if HISTORY else {"message": "no videos yet"}

@app.get("/history")
async def history():
    return HISTORY

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    return {"token": "hf-free-token", "access_token": "hf-free-token"}

def compress_image_for_wan(image_path: str, max_size=1280) -> str:
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            iw, ih = im.size
            if max(iw, ih) > max_size:
                ratio = max_size / max(iw, ih)
                new_w = int(iw * ratio)
                new_h = int(ih * ratio)
                im = im.resize((new_w, new_h), Image.LANCZOS)
                compressed_path = image_path.replace(".", "_wan.")
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGB")
                im.save(compressed_path, "JPEG", quality=90, optimize=True)
                print(f"Wan compress {iw}x{ih} -> {new_w}x{new_h}")
                return compressed_path
    except Exception as e:
        print(f"Wan compress failed: {e}")
    return image_path

@app.post("/generate")
async def generate(
    image: UploadFile = File(..., description="Reference image - first frame"),
    motion_prompt: str = Form(..., description="Motion prompt"),
    prompt: str = Form(None),
    negative_prompt: str = Form(""),
    resolution: str = Form("720"),
    aspect_ratio: str = Form("16:9"),
    orientation: str = Form("landscape"),
    duration: int = Form(5),
    duration_seconds: int = Form(None),
    camera_control: str = Form("static"),
    camera_json: str = Form(None),
    platform: str = Form("wan"),
    x_api_key: str = Header(None, alias="X-API-Key"),
    authorization: str = Header(None)
):
    final_prompt = motion_prompt or prompt or "cinematic smooth motion"
    final_duration = duration_seconds if duration_seconds is not None else duration
    final_duration = max(2, min(10, final_duration))
    final_camera = camera_json if camera_json else camera_control
    
    try:
        res_val = int(resolution)
        if res_val not in [480, 720, 1080]:
            res_val = 720
    except:
        res_val = 720
    
    temp_id = str(uuid.uuid4())
    image_ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    image_filename = f"{temp_id}_input.{image_ext}"
    image_path = f"videos/{image_filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    wan_image_path = compress_image_for_wan(image_path, max_size=1280 if res_val >= 720 else 854)
    
    header_key = ""
    if x_api_key:
        header_key = x_api_key
    elif authorization and "Bearer " in authorization:
        header_key = authorization.replace("Bearer ", "").strip()
    elif authorization:
        header_key = authorization.strip()
    
    hf_key = get_hf_key(header_key)
    
    base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://appimgvid-backend2026.onrender.com"
    video_filename = f"{temp_id}.mp4"
    video_path = f"videos/{video_filename}"
    video_url = f"{base_url}/videos/{video_filename}"
    
    camera_prompt_map = {
        "static": "static camera, locked-off shot, tripod, no camera movement, stable",
        "tilt up": "camera tilt up, smooth upward tilt, cinematic",
        "tilt down": "camera tilt down, smooth downward tilt, cinematic",
        "pan left": "camera pan left, smooth left pan, cinematic",
        "pan right": "camera pan right, smooth right pan, cinematic",
        "orbit": "camera orbit around subject, circular movement, cinematic, 3d parallax",
        "zoom in": "camera zoom in, slow push in, cinematic",
        "zoom out": "camera zoom out, slow pull out, cinematic"
    }
    camera_add = camera_prompt_map.get(final_camera.lower(), final_camera if final_camera != "static" else camera_prompt_map["static"])
    full_prompt = f"{final_prompt}, {camera_add}, cinematic, realistic, highly detailed, 4k, smooth motion, natural movement"
    
    base_negative = "face change, different face, face swap, distorted face, blurry, low quality, low resolution, distorted, ugly, bad anatomy, watermark"
    neg_prompt = f"{negative_prompt}, {base_negative}" if negative_prompt else base_negative
    
    entry = {
        "id": temp_id,
        "videoId": temp_id,
        "video_id": temp_id,
        "videoUrl": "",
        "video_url": "",
        "url": "",
        "status": "queued",
        "progress": 0,
        "prompt": final_prompt,
        "full_prompt": full_prompt,
        "motion_prompt": final_prompt,
        "negative_prompt": neg_prompt,
        "resolution": str(res_val),
        "aspect_ratio": aspect_ratio,
        "duration": final_duration,
        "duration_seconds": final_duration,
        "camera_control": final_camera,
        "platform": "wan2.1-free",
        "model": HF_MODEL if res_val >= 720 else HF_MODEL_FAST,
        "image_path": image_path,
        "wan_image_path": wan_image_path,
        "video_path": video_path,
        "video_url_final": video_url,
        "hf_key_set": bool(hf_key)
    }
    HISTORY.append(entry)
    
    def do_generation():
        try:
            entry["status"] = "processing"
            entry["progress"] = 10
            print(f"[{temp_id}] Starting Wan 2.1: {full_prompt[:120]}")
            
            if not hf_key or "PASTE_YOUR" in hf_key:
                raise Exception("No HF API key set. Set HF_API_KEY env var on Render with your hf_xxx key")
            
            video_bytes = None
            last_error = None
            
            try:
                from huggingface_hub import InferenceClient
                from PIL import Image as PILImage
                
                print(f"[{temp_id}] Trying InferenceClient fal-ai provider...")
                client = InferenceClient(provider="fal-ai", api_key=hf_key)
                entry["progress"] = 20
                
                pil_image = PILImage.open(wan_image_path)
                
                result = client.image_to_video(
                    image=pil_image,
                    prompt=full_prompt,
                    negative_prompt=neg_prompt,
                    model=HF_MODEL if res_val >= 720 else HF_MODEL_FAST,
                )
                print(f"[{temp_id}] result type: {type(result)}")
                
                if isinstance(result, bytes):
                    video_bytes = result
                elif hasattr(result, 'read'):
                    video_bytes = result.read()
                else:
                    import requests as req
                    if isinstance(result, str) and result.startswith("http"):
                        r = req.get(result, timeout=120)
                        video_bytes = r.content
                    else:
                        video_bytes = result
                        
                if video_bytes and len(video_bytes) > 10000:
                    print(f"[{temp_id}] Got video {len(video_bytes)} bytes via fal-ai")
                else:
                    raise Exception(f"Empty result from fal-ai: {result}")
                    
            except Exception as e1:
                print(f"[{temp_id}] fal-ai failed: {e1}")
                traceback.print_exc()
                last_error = str(e1)
                entry["progress"] = 30
                
                try:
                    from huggingface_hub import InferenceClient
                    from PIL import Image as PILImage
                    print(f"[{temp_id}] Trying hf-inference provider...")
                    client2 = InferenceClient(api_key=hf_key)
                    pil_image = PILImage.open(wan_image_path)
                    
                    result = client2.image_to_video(
                        image=pil_image,
                        prompt=full_prompt,
                        model=HF_MODEL,
                    )
                    if isinstance(result, bytes):
                        video_bytes = result
                    elif isinstance(result, str) and result.startswith("http"):
                        import requests as req
                        r = req.get(result, timeout=120)
                        video_bytes = r.content
                    else:
                        video_bytes = result if isinstance(result, bytes) else None
                        
                except Exception as e2:
                    print(f"[{temp_id}] hf-inference failed: {e2}")
                    traceback.print_exc()
                    last_error = str(e2)
                    entry["progress"] = 40
                    
                    try:
                        import requests as req
                        print(f"[{temp_id}] Trying direct HF API...")
                        api_url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
                        headers = {"Authorization": f"Bearer {hf_key}"}
                        
                        with open(wan_image_path, "rb") as f:
                            img_data = f.read()
                        
                        response = req.post(api_url, headers=headers, data=img_data, timeout=300)
                        print(f"[{temp_id}] Direct API {response.status_code}")
                        
                        if response.status_code == 200 and len(response.content) > 10000:
                            video_bytes = response.content
                        else:
                            raise Exception(f"Direct API failed: {response.status_code} {response.text[:1000]}")
                            
                    except Exception as e3:
                        print(f"[{temp_id}] Direct API failed: {e3}")
                        last_error = str(e3)
            
            if not video_bytes or len(video_bytes) < 10000:
                raise Exception(f"All HF methods failed. Last error: {last_error}. Check HF token has Inference permission.")
            
            with open(video_path, "wb") as f:
                f.write(video_bytes)
            
            size = os.path.getsize(video_path)
            print(f"[{temp_id}] Saved {video_path} {size} bytes")
            
            if size < 10000:
                raise Exception(f"Video too small {size} bytes")
            
            entry["videoUrl"] = video_url
            entry["video_url"] = video_url
            entry["url"] = video_url
            entry["status"] = "completed"
            entry["progress"] = 100
            print(f"[{temp_id}] Completed: {video_url}")
            
        except Exception as e:
            print(f"[{temp_id}] Failed: {e}")
            traceback.print_exc()
            entry["status"] = "failed"
            entry["error"] = str(e)
            entry["progress"] = 0
    
    import threading
    threading.Thread(target=do_generation, daemon=True).start()
    
    return {
        "id": temp_id,
        "videoId": temp_id,
        "video_id": temp_id,
        "status": "queued",
        "message": f"Wan 2.1 generation started - cinematic {res_val}p, {final_duration}s - poll /status/{temp_id}",
        "videoUrl": None,
        "video_url": None,
        "url": None,
        "poll_url": f"/status/{temp_id}",
        "model": HF_MODEL,
        "free": True
    }

@app.get("/status/{video_id}")
async def get_status(video_id: str):
    for entry in reversed(HISTORY):
        if entry["id"] == video_id or entry.get("videoId") == video_id:
            return entry
    return {"error": "not found", "id": video_id}

@app.get("/video/{video_id}")
async def get_video(video_id: str):
    for entry in reversed(HISTORY):
        if entry["id"] == video_id or entry.get("videoId") == video_id:
            return entry
    return {"error": "not found", "id": video_id}
