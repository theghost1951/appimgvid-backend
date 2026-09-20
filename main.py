
"""
REAL Agnes AI integration for https://appimgvid-backend2026.onrender.com
Now with actual motion - image-to-video via Agnes Video v2.0

Deploy this as main.py
Set AGNES_API_KEY in Render Env Vars
"""

import os
import shutil
import uuid
import json
import time
import requests

from fastapi import FastAPI, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AppImgVid2 Backend - Agnes AI Real")

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

# ===== PERMANENT KEY - PASTE YOUR KEY HERE =====
HARDCODED_AGNES_KEY = "PASTE_YOUR_AGNES_KEY_HERE"  # <-- REPLACE THIS WITH YOUR REAL KEY LIKE "sk-..."
# If you leave this as PASTE_YOUR... you will get static videos with no motion!
# ===============================================

AGNES_BASE_CREATE = "https://apihub.agnes-ai.com/v1/videos"
AGNES_BASE_GET = "https://apihub.agnes-ai.com/agnesapi"


def upload_image_via_agnes(image_path: str, api_key: str) -> str:
    """Upload local image to Agnes Image API to get hosted URL that Video API can fetch"""
    import base64
    try:
        with open(image_path, 'rb') as f:
            raw = f.read()
            b64 = base64.b64encode(raw).decode('utf-8')
        ext = image_path.split('.')[-1].lower()
        mime = 'image/jpeg' if ext in ['jpg','jpeg'] else 'image/png' if ext == 'png' else 'image/webp'
        data_uri = f"data:{mime};base64,{b64}"
        print(f"Uploading image to Agnes Image API, original {len(raw)//1024}KB, data URI {len(data_uri)//1000}KB")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        # Try with different payloads - first try exact same size preservation
        # Get image dimensions via Pillow if available
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
                # Use closest supported size
                size_str = f"{w}x{h}"
                print(f"Original image size: {size_str}")
        except:
            size_str = "768x1280"  # portrait default
        
        payloads = [
            {
                "model": "agnes-image-2.1-flash",
                "prompt": "preserve original composition exactly, no changes, high quality, keep same",
                "size": size_str,
                "extra_body": {
                    "image": [data_uri],
                    "response_format": "url"
                }
            },
            {
                "model": "agnes-image-2.1-flash",
                "prompt": "keep same image",
                "size": "1024x1024",
                "extra_body": {
                    "image": [data_uri],
                    "response_format": "url"
                }
            }
        ]
        
        for payload in payloads:
            try:
                print(f"Trying Agnes image upload with size {payload['size']}")
                r = requests.post("https://apihub.agnes-ai.com/v1/images/generations", headers=headers, json=payload, timeout=180)
                print(f"Agnes Image upload response: {r.status_code} {r.text[:3000]}")
                if r.status_code == 200:
                    data = r.json()
                    if 'data' in data and len(data['data']) > 0:
                        url = data['data'][0].get('url')
                        if url:
                            print(f"Agnes hosted image URL: {url}")
                            return url
                    if 'url' in data:
                        return data['url']
                else:
                    print(f"Agnes image upload failed payload {payload['size']}: {r.text[:1000]}")
            except Exception as inner_e:
                print(f"Payload {payload['size']} error: {inner_e}")
                continue
                
    except Exception as e:
        import traceback
        print(f"Agnes image upload failed: {e}")
        print(traceback.format_exc())
    return None

def upload_to_0x0(image_path: str) -> str:
    """Upload to 0x0.st - very reliable, no block"""
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            r = requests.post('https://0x0.st', files=files, timeout=30)
            if r.status_code == 200 and r.text.startswith('http'):
                url = r.text.strip()
                print(f"0x0.st upload OK: {url}")
                return url
            print(f"0x0.st failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"0x0.st error: {e}")
    return None

def upload_to_fileio(image_path: str) -> str:
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            r = requests.post('https://file.io', files=files, timeout=30)
            if r.status_code == 200:
                data = r.json()
                link = data.get('link')
                if link:
                    print(f"file.io upload OK: {link}")
                    return link
    except Exception as e:
        print(f"file.io error: {e}")
    return None


def upload_image_public(image_path: str, api_key: str = "") -> str:
    """Fallback: try multiple hosts"""
    # Try 0x0.st first - most reliable
    url = upload_to_0x0(image_path)
    if url:
        return url
    url = upload_to_fileio(image_path)
    if url:
        return url
    try:
        # Try catbox.moe
        with open(image_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload'}
            r = requests.post('https://catbox.moe/user/api.php', data=data, files=files, timeout=30)
            if r.status_code == 200 and r.text.startswith('https://'):
                url = r.text.strip()
                print(f"Catbox upload OK: {url}")
                return url
            print(f"Catbox failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"Catbox upload error: {e}")
    
    try:
        # Fallback: tmpfiles.org
        with open(image_path, 'rb') as f:
            files = {'file': f}
            r = requests.post('https://tmpfiles.org/api/v1/upload', files=files, timeout=30)
            if r.status_code == 200:
                data = r.json()
                url = data.get('data', {}).get('url', '')
                if url:
                    # Convert https://tmpfiles.org/dl/xxx to https://tmpfiles.org/dl/xxx direct
                    # Actually need direct download link: replace /dl/ with direct? tmpfiles gives page, but we need direct
                    # Use the url and replace to get direct
                    direct = url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    print(f"Tmpfiles upload OK: {direct}")
                    return direct
    except Exception as e:
        print(f"Tmpfiles upload error: {e}")

    # Last fallback: use Render URL (will likely timeout but try)
    base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://appimgvid-backend2026.onrender.com"
    filename = os.path.basename(image_path)
    fallback = f"{base_url}/videos/{filename}"
    print(f"Using fallback Render URL: {fallback}")
    return fallback



def get_agnes_key(header_key: str = ""):
    # 1. Header from APK, 2. Render Env Var, 3. Hardcoded in code
    return header_key or os.getenv("AGNES_API_KEY") or os.getenv("AGNES_KEY") or HARDCODED_AGNES_KEY or ""

@app.get("/")
async def root():
    return {"status": "ok", "service": "AppImgVid2 Agnes AI Real", "endpoints": ["/generate", "/history", "/latest", "/login"], "agnes_key_set": bool(get_agnes_key())}

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
    image: UploadFile = File(..., description="Reference image"),
    motion_prompt: str = Form(..., description="Motion prompt"),
    prompt: str = Form(None),
    negative_prompt: str = Form(""),
    resolution: str = Form("1080"),
    aspect_ratio: str = Form("16:9"),
    orientation: str = Form("landscape"),
    duration: int = Form(8),
    duration_seconds: int = Form(None),
    camera_control: str = Form("static"),
    camera_json: str = Form(None),
    platform: str = Form("agnes"),
    x_api_key: str = Header(None, alias="X-API-Key"),
    authorization: str = Header(None)
):
    final_prompt = motion_prompt or prompt or ""
    final_duration = duration_seconds if duration_seconds is not None else duration
    final_camera = camera_json if camera_json else camera_control
    
    # NEW: 1) Use reference image as first frame, 2) Auto aspect from image, 3) 720p fixed
    def get_dimensions_from_image(image_path, aspect_str, forced_res=720):
        """Use actual image dimensions to preserve exact aspect ratio, supports 480/720/1080"""
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                iw, ih = im.size
                print(f"Input image real size: {iw}x{ih} ratio {iw/ih:.3f}")
                img_ratio = iw / ih if ih != 0 else 16/9
                # Preserve exact ratio at chosen resolution
                if img_ratio >= 1:  # landscape or square
                    h = forced_res
                    w = int(h * img_ratio)
                else:  # portrait
                    w = forced_res
                    h = int(w / img_ratio)
                # Make divisible by 16 (Agnes requirement)
                w = (w // 16) * 16
                h = (h // 16) * 16
                # Clamp based on resolution tier
                max_side = 1920 if forced_res == 1080 else 1280 if forced_res == 720 else 854
                if w > max_side and img_ratio >= 1:
                    w = max_side
                    h = int(max_side / img_ratio)
                    h = (h // 16) * 16
                if h > max_side and img_ratio < 1:
                    h = max_side
                    w = int(max_side * img_ratio)
                    w = (w // 16) * 16
                print(f"Preserving input ratio -> output {w}x{h} at {forced_res}p")
                return (w, h)
        except Exception as e:
            print(f"Could not read image size, fallback to aspect {aspect_str}: {e}")
        
        # Fallback to aspect string mapping at chosen resolution
        try:
            if ":" in aspect_str:
                w_ratio, h_ratio = map(float, aspect_str.split(":"))
            else:
                w_ratio, h_ratio = 16, 9
            res_val = forced_res
            if w_ratio >= h_ratio:
                h = res_val
                w = int(res_val * w_ratio / h_ratio)
            else:
                w = res_val
                h = int(res_val * h_ratio / w_ratio)
            w = (w // 16) * 16
            h = (h // 16) * 16
            return (w, h)
        except:
            return (1280, 720)

    # Resolution choices 480p, 720p, 1080p - keep client choice
    # Default to 720 if invalid
    try:
        res_val = int(resolution)
        if res_val not in [480, 720, 1080]:
            res_val = 720
    except:
        res_val = 720
    resolution = str(res_val)
    # width, height computed AFTER image saved (need image_path first)
    # Placeholder, will recompute after save
    width, height = (1280, 720)  # temp, overwritten after image save
    print(f"Resolution {resolution}p chosen, aspect will be auto-detected from reference image (first frame)")

    frame_rate = 24
    num_frames = final_duration * frame_rate
    num_frames = ((num_frames // 8) * 8) + 1
    if num_frames > 481:  # 20s *24 = 480 +1 = 481 max for v2.0 (5-20s)
        num_frames = 481
    if num_frames < 9:
        num_frames = 9

    temp_id = str(uuid.uuid4())
    
    image_ext = image.filename.split(".")[-1] if "." in image.filename else "png"
    image_filename = f"{temp_id}_input.{image_ext}"
    image_path = f"videos/{image_filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    # NOW compute exact dimensions from saved image - this is the first frame, with chosen resolution 480/720/1080
    width, height = get_dimensions_from_image(image_path, aspect_ratio, forced_res=res_val)
    print(f"FINAL: Using reference as first frame, auto aspect {aspect_ratio} -> {width}x{height} at {resolution}p")
    
    base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://appimgvid-backend2026.onrender.com"
    
    header_key = ""
    if x_api_key:
        header_key = x_api_key
    elif authorization and "Bearer " in authorization:
        header_key = authorization.replace("Bearer ", "").strip()
    elif authorization:
        header_key = authorization.strip()
    agnes_key = get_agnes_key(header_key)
    if not agnes_key or "PASTE_YOUR" in agnes_key:
        print("WARNING: No Agnes key set! Will create static video with no motion!")
        print("Please paste your real key in HARDCODED_AGNES_KEY at top of main.py")


    video_filename = f"{temp_id}.mp4"
    video_path = f"videos/{video_filename}"
    video_url = f"{base_url}/videos/{video_filename}"

    entry = {
        "id": temp_id,
        "videoId": temp_id,
        "videoUrl": "",
        "video_url": "",
        "url": "",
        "status": "queued",
        "progress": 0,
        "prompt": final_prompt,
        "motion_prompt": final_prompt,
        "negative_prompt": negative_prompt,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "orientation": orientation,
        "duration": final_duration,
        "camera_control": final_camera,
        "platform": platform,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "image_path": image_path,
        "video_path": video_path,
        "video_url_final": video_url
    }
    HISTORY.append(entry)

    def do_generation():
        try:
            agnes_hosted = upload_image_via_agnes(image_path, agnes_key)
            if agnes_hosted:
                public_image_url = agnes_hosted
            else:
                public_image_url = upload_image_public(image_path, agnes_key)
            print(f"Public image for Agnes: {public_image_url}")

            if not agnes_key:
                print("No key, static placeholder")
                try:
                    import subprocess
                    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-c:v", "libx264", "-t", str(final_duration), "-pix_fmt", "yuv420p", "-vf", f"scale={width}:-2", video_path]
                    subprocess.run(cmd, capture_output=True, timeout=30)
                except:
                    shutil.copy(image_path, video_path)
                entry["videoUrl"] = video_url
                entry["video_url"] = video_url
                entry["url"] = video_url
                entry["status"] = "completed"
                entry["progress"] = 100
                return

            headers = {
                "Authorization": f"Bearer {agnes_key}",
                "Content-Type": "application/json"
            }
            
            full_prompt = final_prompt
            neg_prompt = negative_prompt
            if final_camera == "static":
                full_prompt = f"{final_prompt}, static camera, fixed camera position, no camera movement, locked-off shot, tripod"
                if "camera movement" not in neg_prompt.lower():
                    neg_prompt = (neg_prompt + ", camera movement, camera shake, panning, tilting, zooming").strip(", ")
            elif final_camera and final_camera != "static":
                full_prompt = f"{final_prompt}, camera {final_camera}"
            
            payload = {
                "model": "agnes-video-v2.0",
                "prompt": full_prompt,
                "image": public_image_url,
                "width": width,
                "height": height,
                "num_frames": num_frames,
                "frame_rate": frame_rate
            }
            if neg_prompt:
                payload["negative_prompt"] = neg_prompt

            print(f"Calling Agnes create")
            resp = requests.post(AGNES_BASE_CREATE, headers=headers, json=payload, timeout=120)
            print(f"Agnes create response: {resp.status_code} {resp.text[:2000]}")
            
            if resp.status_code != 200:
                raise Exception(f"Agnes create failed {resp.status_code}: {resp.text}")
            
            data = resp.json()
            video_id_agnes = data.get("video_id") or data.get("id") or data.get("task_id")
            if not video_id_agnes:
                raise Exception(f"No video_id: {data}")
            
            entry["agnes_video_id"] = video_id_agnes
            entry["status"] = "in_progress"

            agnes_video_url = None
            # Polling scales with duration: 5s~90, 10s~150, 20s~250 attempts
            if final_duration <= 5:
                max_attempts = 90   # 450s
            elif final_duration <= 10:
                max_attempts = 150  # 750s
            else:
                max_attempts = 250  # 1250s = ~20 mins for 20s clip
            print(f"Polling max {max_attempts} attempts for {final_duration}s video ({num_frames} frames)")
            for attempt in range(max_attempts):
                time.sleep(5)
                try:
                    poll_url = f"{AGNES_BASE_GET}?video_id={video_id_agnes}&model_name=agnes-video-v2.0"
                    poll_resp = requests.get(poll_url, headers={"Authorization": f"Bearer {agnes_key}"}, timeout=30)
                    print(f"Poll {attempt}: {poll_resp.text[:1000]}")
                    
                    if poll_resp.status_code == 200:
                        poll_data = poll_resp.json()
                        status = poll_data.get("status") or poll_data.get("state")
                        progress = poll_data.get("progress", 0)
                        entry["progress"] = progress
                        entry["status"] = status or "in_progress"
                        
                        for field in ["remixed_from_video_id", "video_url", "url", "result_url", "output_url", "videoUrl"]:
                            if field in poll_data and poll_data[field]:
                                agnes_video_url = poll_data[field]
                                break
                        
                        if not agnes_video_url:
                            if "data" in poll_data and isinstance(poll_data["data"], dict):
                                for field in ["remixed_from_video_id", "video_url", "url"]:
                                    if field in poll_data["data"]:
                                        agnes_video_url = poll_data["data"][field]
                                        break
                        
                        if not agnes_video_url and status in ["completed", "success", "done", "finished"]:
                            txt = json.dumps(poll_data)
                            import re
                            m = re.search(r'https://[^\s"\']+\.mp4', txt)
                            if m:
                                agnes_video_url = m.group(0)
                        
                        if agnes_video_url:
                            print(f"Found Agnes video URL: {agnes_video_url}")
                            break
                        
                        if status in ["failed", "error"]:
                            raise Exception(f"Agnes failed: {poll_data}")
                            
                except Exception as e:
                    print(f"Poll error {attempt}: {e}")
                    continue
            
            if not agnes_video_url:
                raise Exception("No video URL after polling")
            
            print(f"Downloading {agnes_video_url}")
            try:
                r = requests.get(agnes_video_url, stream=True, timeout=120)
                r.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                size = os.path.getsize(video_path)
                print(f"Saved {video_path} {size} bytes")
                if size < 10000:
                    print(f"WARNING: File too small, might be failed download")
            except Exception as dl_e:
                print(f"Download failed: {dl_e}, will use Agnes direct URL as fallback")
            
            # Store both local and direct URLs
            entry["videoUrl"] = video_url
            entry["video_url"] = video_url
            entry["url"] = video_url
            entry["agnes_direct_url"] = agnes_video_url
            entry["direct_url"] = agnes_video_url
            entry["status"] = "completed"
            entry["progress"] = 100
            print(f"Completed entry: local {video_url} direct {agnes_video_url}")
            
        except Exception as e:
            import traceback
            print(f"BG failed: {e}")
            print(traceback.format_exc())
            entry["status"] = "failed"
            entry["error"] = str(e)
            # Only create static placeholder if NO key (expected behavior)
            # If key exists but Agnes failed, DON'T create static - show failed so user knows
            if not agnes_key:
                try:
                    import subprocess
                    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-c:v", "libx264", "-t", str(final_duration), "-pix_fmt", "yuv420p", "-vf", f"scale={width}:-2", video_path]
                    subprocess.run(cmd, capture_output=True, timeout=30)
                    if not os.path.exists(video_path):
                        shutil.copy(image_path, video_path)
                    entry["videoUrl"] = video_url
                    entry["video_url"] = video_url
                    entry["url"] = video_url
                    entry["status"] = "completed"
                except:
                    pass
            else:
                print("Agnes failed but key exists - NOT creating static fallback, returning failed status")
                # Leave videoUrl empty so APK shows error not static video

    import threading
    threading.Thread(target=do_generation, daemon=True).start()

    return {
        "id": temp_id,
        "videoId": temp_id,
        "video_id": temp_id,
        "status": "queued",
        "message": "Generation started, poll /status/{id}",
        "videoUrl": None,
        "video_url": None,
        "url": None,
        "poll_url": f"/status/{temp_id}"
    }

@app.get("/status/{video_id}")
async def get_status(video_id: str):
    for entry in reversed(HISTORY):
        if entry["id"] == video_id or entry.get("videoId") == video_id:
            # If local file missing, return direct Agnes URL as fallback
            video_path = entry.get("video_path")
            if video_path and not os.path.exists(video_path):
                print(f"Local file missing {video_path}, returning direct URL")
                if entry.get("agnes_direct_url"):
                    entry["videoUrl"] = entry["agnes_direct_url"]
                    entry["video_url"] = entry["agnes_direct_url"]
            return entry
    return {"error": "not found", "id": video_id}

@app.get("/video/{video_id}")
async def get_video(video_id: str):
    for entry in reversed(HISTORY):
        if entry["id"] == video_id or entry.get("videoId") == video_id:
            return entry
    return {"error": "not found", "id": video_id}

