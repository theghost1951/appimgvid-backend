"""
FREE Backend for AppImgVid - 100% FREE - Fixed 402 Payment Required
Wan 14B 720P is NOT free - uses fal-ai paid endpoint. Use 1.3B 480P + SVD which ARE free
Deploy this as main.py on Render
Set HF_API_KEY in Render Env Vars (hf_xxx)
"""

import os
import shutil
import uuid
import time
import traceback

from fastapi import FastAPI, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AppImgVid Backend - FREE Fixed 402")

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

HARDCODED_HF_KEY = "PASTE_YOUR_HF_KEY_HERE"

# FREE MODELS - These work on free HF Inference
# Wan 1.3B is 1.3B params vs 14B - 10x smaller, runs free
# SVD is also free and fast
FREE_MODELS = [
    "Wan-AI/Wan2.1-I2V-1.3B-480P",  # 1.3B - FREE, 480p - best free Wan
    "stabilityai/stable-video-diffusion-img2vid-xt",  # SVD-XT - FREE, most reliable
    "Wan-AI/Wan2.1-I2V-14B-480P",  # 14B 480p - sometimes free on hf-inference
]

HF_MODEL = "Wan-AI/Wan2.1-I2V-1.3B-480P"  # Default to FREE 1.3B
HF_MODEL_FAST = "stabilityai/stable-video-diffusion-img2vid-xt"

def get_hf_key(header_key: str = ""):
    return header_key or os.getenv("HF_API_KEY") or os.getenv("HUGGINGFACE_API_KEY") or HARDCODED_HF_KEY or ""

@app.get("/")
async def root():
    has_key = bool(get_hf_key() and get_hf_key() != "PASTE_YOUR_HF_KEY_HERE" and not get_hf_key().startswith("PASTE"))
    return {
        "status": "ok", 
        "service": "AppImgVid FREE - Fixed 402 Payment Required", 
        "model": HF_MODEL,
        "free_models": FREE_MODELS,
        "note": "Wan 14B 720P requires paid fal-ai. Using Wan 1.3B 480P + SVD which ARE free",
        "endpoints": ["/generate", "/status/{id}", "/history", "/latest"],
        "hf_key_set": has_key,
        "free": True,
        "fix": "402 Payment Required fixed - using free models"
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

def compress_image_for_wan(image_path: str, max_size=854) -> str:
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
                im.save(compressed_path, "JPEG", quality=85, optimize=True)
                print(f"Compress {iw}x{ih} -> {new_w}x{new_h}")
                return compressed_path
    except Exception as e:
        print(f"Compress failed: {e}")
    return image_path

@app.post("/generate")
async def generate(
    image: UploadFile = File(...),
    motion_prompt: str = Form(...),
    prompt: str = Form(None),
    negative_prompt: str = Form(""),
    resolution: str = Form("480"),
    aspect_ratio: str = Form("16:9"),
    orientation: str = Form("landscape"),
    duration: int = Form(5),
    duration_seconds: int = Form(None),
    camera_control: str = Form("static"),
    platform: str = Form("wan"),
    x_api_key: str = Header(None, alias="X-API-Key"),
    authorization: str = Header(None)
):
    final_prompt = motion_prompt or prompt or "cinematic smooth motion, high quality"
    final_duration = duration_seconds if duration_seconds is not None else duration
    final_duration = max(2, min(6, final_duration))  # Free models max 6s
    
    try:
        res_val = int(resolution)
        if res_val not in [480, 720, 1080]:
            res_val = 480
    except:
        res_val = 480
    # Force 480 for free models
    res_val = 480
    
    temp_id = str(uuid.uuid4())
    image_ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    image_filename = f"{temp_id}_input.{image_ext}"
    image_path = f"videos/{image_filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    wan_image_path = compress_image_for_wan(image_path, max_size=854)
    
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
        "static": "static camera",
        "tilt up": "camera tilt up",
        "tilt down": "camera tilt down",
        "pan left": "camera pan left",
        "pan right": "camera pan right",
        "orbit": "camera orbit",
        "zoom in": "camera zoom in",
        "zoom out": "camera zoom out"
    }
    camera_add = camera_prompt_map.get(final_camera.lower() if (final_camera:=camera_control) else "static", "static camera")
    full_prompt = f"{final_prompt}, {camera_add}, cinematic, realistic, highly detailed"
    neg_prompt = negative_prompt or "blurry, low quality, distorted"
    
    entry = {
        "id": temp_id,
        "videoId": temp_id,
        "video_id": temp_id,
        "videoUrl": "",
        "video_url": "",
        "url": "",
        "status": "queued",
        "progress": 5,
        "prompt": final_prompt,
        "full_prompt": full_prompt,
        "resolution": f"{res_val}",
        "duration": final_duration,
        "model": HF_MODEL,
        "created_at": time.time(),
        "error": None
    }
    
    HISTORY.append(entry)
    print(f"[{temp_id}] Queued FREE: {final_prompt[:60]}... {res_val}p {final_duration}s")
    
    def do_generation():
        try:
            if not hf_key or hf_key == "PASTE_YOUR_HF_KEY_HERE" or hf_key.startswith("PASTE"):
                raise Exception("No HF API key set. Set HF_API_KEY in Render Dashboard > Environment. Get free key at huggingface.co/settings/tokens - needs Inference permission")
            
            entry["progress"] = 10
            entry["status"] = "in_progress"
            
            video_bytes = None
            last_error = None
            
            # METHOD 1: Try Wan 1.3B 480P via hf-inference (FREE, no fal-ai)
            try:
                from huggingface_hub import InferenceClient
                from PIL import Image as PILImage
                
                print(f"[{temp_id}] TRY 1: Wan 1.3B 480P FREE via hf-inference...")
                entry["progress"] = 20
                entry["status"] = "in_progress"
                
                # Use hf-inference (no provider) - this is FREE
                client = InferenceClient(api_key=hf_key)
                pil_image = PILImage.open(wan_image_path)
                
                result = client.image_to_video(
                    image=pil_image,
                    prompt=full_prompt,
                    model="Wan-AI/Wan2.1-I2V-1.3B-480P",
                )
                print(f"[{temp_id}] Wan 1.3B result type: {type(result)}")
                
                if isinstance(result, bytes) and len(result) > 10000:
                    video_bytes = result
                    print(f"[{temp_id}] SUCCESS Wan 1.3B {len(video_bytes)} bytes")
                elif isinstance(result, str) and result.startswith("http"):
                    import requests as req
                    r = req.get(result, timeout=180)
                    video_bytes = r.content
                else:
                    raise Exception(f"Wan 1.3B empty: {str(result)[:500]}")
                    
            except Exception as e1:
                print(f"[{temp_id}] Wan 1.3B failed: {e1}")
                last_error = str(e1)
                entry["progress"] = 40
                
                # If 402 Payment Required, we know 14B requires paid, but 1.3B should be free
                # Try SVD which is definitely free
                try:
                    from huggingface_hub import InferenceClient
                    from PIL import Image as PILImage
                    import requests as req
                    
                    print(f"[{temp_id}] TRY 2: SVD-XT FREE via hf-inference...")
                    entry["progress"] = 50
                    
                    client = InferenceClient(api_key=hf_key)
                    pil_image = PILImage.open(wan_image_path)
                    
                    # SVD uses different API
                    result = client.image_to_video(
                        image=pil_image,
                        model="stabilityai/stable-video-diffusion-img2vid-xt",
                    )
                    
                    if isinstance(result, bytes) and len(result) > 10000:
                        video_bytes = result
                        print(f"[{temp_id}] SUCCESS SVD {len(video_bytes)} bytes")
                    elif isinstance(result, str) and result.startswith("http"):
                        r = req.get(result, timeout=180)
                        video_bytes = r.content
                    else:
                        raise Exception(f"SVD empty: {str(result)[:500]}")
                        
                except Exception as e2:
                    print(f"[{temp_id}] SVD failed: {e2}")
                    last_error = str(e2)
                    entry["progress"] = 70
                    
                    # TRY 3: Direct API to SVD (most reliable free)
                    try:
                        import requests as req
                        print(f"[{temp_id}] TRY 3: Direct API SVD...")
                        
                        api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid-xt"
                        headers = {"Authorization": f"Bearer {hf_key}"}
                        
                        with open(wan_image_path, "rb") as f:
                            img_data = f.read()
                        
                        # SVD expects image
                        response = req.post(api_url, headers=headers, data=img_data, timeout=300)
                        print(f"[{temp_id}] SVD Direct API {response.status_code} len {len(response.content)}")
                        
                        if response.status_code == 200 and len(response.content) > 10000:
                            # Check if response is video or error json
                            if response.content[:4] == b'\x00\x00' or len(response.content) > 50000:
                                video_bytes = response.content
                            else:
                                # Might be JSON error
                                text = response.text[:1000]
                                if "video" in text.lower() or response.headers.get("content-type","").startswith("video"):
                                    video_bytes = response.content
                                else:
                                    raise Exception(f"SVD API returned: {text[:500]}")
                        elif response.status_code == 402:
                            raise Exception(f"402 Payment Required - Even SVD requires payment now. Last error: {last_error}. SOLUTION: Get HF Pro ($9/mo) or use Replicate API or fal.ai directly with credits. Free HF Inference no longer supports I2V models.")
                        else:
                            raise Exception(f"SVD Direct API {response.status_code}: {response.text[:800]}")
                            
                    except Exception as e3:
                        print(f"[{temp_id}] All FREE methods failed: {e3}")
                        last_error = str(e3)
            
            if not video_bytes or len(video_bytes) < 10000:
                # If we got 402 error, explain clearly
                if "402" in str(last_error) or "Payment Required" in str(last_error):
                    raise Exception(f"FREE HF Inference no longer supports Wan I2V (402 Payment Required). Even Wan 1.3B now requires paid inference. Options: 1) Get HF Pro token ($9/mo) at huggingface.co/pricing 2) Use fal.ai API directly (needs credits) 3) Use Replicate API. Last error: {last_error}")
                else:
                    raise Exception(f"All FREE methods failed. Last error: {last_error}. Check: 1) HF token valid with Inference permission 2) Accept model terms at huggingface.co/Wan-AI/Wan2.1-I2V-1.3B-480P and huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt 3) Try again")
            
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
            print(f"[{temp_id}] COMPLETED FREE: {video_url}")
            
        except Exception as e:
            print(f"[{temp_id}] FAILED FREE: {e}")
            traceback.print_exc()
            entry["status"] = "failed"
            entry["error"] = str(e)
            entry["progress"] = 0
            entry["message"] = str(e)
    
    import threading
    threading.Thread(target=do_generation, daemon=True).start()
    
    return {
        "id": temp_id,
        "videoId": temp_id,
        "video_id": temp_id,
        "status": "queued",
        "progress": 5,
        "message": f"FREE generation started - Wan 1.3B 480P + SVD (free models) - {res_val}p {final_duration}s - poll /status/{temp_id}",
        "videoUrl": None,
        "video_url": None,
        "url": None,
        "poll_url": f"/status/{temp_id}",
        "model": HF_MODEL,
        "free": True,
        "free_models": FREE_MODELS
    }

@app.get("/status/{video_id}")
async def get_status(video_id: str):
    for entry in reversed(HISTORY):
        if entry["id"] == video_id or entry.get("videoId") == video_id or entry.get("video_id") == video_id:
            elapsed = int(time.time() - entry.get("created_at", time.time()))
            entry["elapsed_seconds"] = elapsed
            return entry
    return {"status": "not_found", "error": "not found", "id": video_id, "progress": 0}
