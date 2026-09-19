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
HARDCODED_AGNES_KEY = "PASTE_YOUR_AGNES_KEY_HERE"  # e.g. "sk_..." 
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
    
    # Map aspect ratio to width/height
    # 9:16 portrait 720x1280, 16:9 landscape 1280x720
    is_portrait = aspect_ratio in ["9:16", "3:4", "2:3"]
    if resolution == "640":
        width, height = (640, 1152) if is_portrait else (1152, 640)
    elif resolution == "720":
        width, height = (720, 1280) if is_portrait else (1280, 720)
    else: # 1080
        width, height = (1080, 1920) if is_portrait else (1920, 1080)

    # Calculate frames: 8n+1 rule, 24fps
    # duration 5s * 24fps = 120 frames -> 121 (8n+1)
    frame_rate = 24
    num_frames = final_duration * frame_rate
    # Adjust to 8n+1
    num_frames = ((num_frames // 8) * 8) + 1
    if num_frames > 441:
        num_frames = 441
    if num_frames < 9:
        num_frames = 9

    temp_id = str(uuid.uuid4())
    
    # Save uploaded image to videos/ so it has public URL for Agnes
    image_ext = image.filename.split(".")[-1] if "." in image.filename else "png"
    image_filename = f"{temp_id}_input.{image_ext}"
    image_path = f"videos/{image_filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    
    base_url = os.getenv("RENDER_EXTERNAL_URL") or "https://appimgvid-backend2026.onrender.com"
    
    # Try header from APK first, then env var - MUST be before upload
    header_key = ""
    if x_api_key:
        header_key = x_api_key
    elif authorization and "Bearer " in authorization:
        header_key = authorization.replace("Bearer ", "").strip()
    elif authorization:
        header_key = authorization.strip()
    agnes_key = get_agnes_key(header_key)
    print(f"Key source: header={bool(header_key)} env={bool(os.getenv('AGNES_API_KEY'))} final_len={len(agnes_key)}")
    print(f"DEBUG: agnes_key length={len(agnes_key)} starts_with={agnes_key[:10] if agnes_key else 'EMPTY'}")

    # Upload to fast public host for Agnes
    # Try Agnes hosted upload first (most reliable for video API)
    agnes_hosted = upload_image_via_agnes(image_path, agnes_key)
    if agnes_hosted:
        public_image_url = agnes_hosted
    else:
        public_image_url = upload_image_public(image_path, agnes_key)
    print(f"Public image for Agnes: {public_image_url}")

    print(f"[GENERATE] id={temp_id} prompt={final_prompt[:200]} {width}x{height} frames={num_frames} image_url={public_image_url}")
    video_filename = f"{temp_id}.mp4"
    video_path = f"videos/{video_filename}"
    video_url = f"{base_url}/videos/{video_filename}"

    if not agnes_key:
        print("No AGNES_API_KEY set, creating static placeholder")
        try:
            import subprocess
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-c:v", "libx264", "-t", str(final_duration), "-pix_fmt", "yuv420p", "-vf", f"scale={width}:-2", video_path]
            subprocess.run(cmd, capture_output=True, timeout=30)
        except Exception as e:
            print(f"ffmpeg failed: {e}")
            shutil.copy(image_path, video_path)
    else:
        # REAL AGNES CALL
        try:
            headers = {
                "Authorization": f"Bearer {agnes_key}",
                "Content-Type": "application/json"
            }
            
            # Combine motion prompt + camera control
            full_prompt = final_prompt
            if final_camera and final_camera != "static":
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
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt

            print(f"Calling Agnes create: {AGNES_BASE_CREATE} payload={json.dumps(payload)[:500]}")
            
            resp = requests.post(AGNES_BASE_CREATE, headers=headers, json=payload, timeout=120)
            print(f"Agnes create response: {resp.status_code} {resp.text[:2000]}")
            
            if resp.status_code != 200:
                raise Exception(f"Agnes create failed {resp.status_code}: {resp.text}")
            
            data = resp.json()
            video_id = data.get("video_id") or data.get("id") or data.get("task_id")
            if not video_id:
                raise Exception(f"No video_id in response: {data}")
            
            print(f"Agnes video_id: {video_id}, polling...")

            # Poll for result - GET https://apihub.agnes-ai.com/agnesapi?video_id=xxx
            agnes_video_url = None
            for attempt in range(60):  # up to 60 * 5s = 5 minutes
                time.sleep(5)
                try:
                    poll_url = f"{AGNES_BASE_GET}?video_id={video_id}&model_name=agnes-video-v2.0"
                    poll_resp = requests.get(poll_url, headers={"Authorization": f"Bearer {agnes_key}"}, timeout=30)
                    print(f"Poll {attempt}: {poll_resp.status_code} {poll_resp.text[:1000]}")
                    
                    if poll_resp.status_code == 200:
                        poll_data = poll_resp.json()
                        # Check various possible fields for video URL
                        # According to docs, result contains video URL
                        status = poll_data.get("status") or poll_data.get("state")
                        progress = poll_data.get("progress", 0)
                        
                        # Try to find video URL - per docs field is remixed_from_video_id or url
                        possible_url_fields = ["remixed_from_video_id", "video_url", "url", "result_url", "output_url", "videoUrl"]
                        for field in possible_url_fields:
                            if field in poll_data and poll_data[field]:
                                agnes_video_url = poll_data[field]
                                break
                        
                        # Sometimes URL is nested
                        if not agnes_video_url:
                            if "data" in poll_data and isinstance(poll_data["data"], dict):
                                for field in possible_url_fields:
                                    if field in poll_data["data"]:
                                        agnes_video_url = poll_data["data"][field]
                                        break
                            if "result" in poll_data and isinstance(poll_data["result"], dict):
                                for field in possible_url_fields:
                                    if field in poll_data["result"]:
                                        agnes_video_url = poll_data["result"][field]
                                        break
                        
                        # If status completed and no URL, try to parse all strings containing http and mp4
                        if not agnes_video_url and status in ["completed", "success", "done", "finished"]:
                            # Look for any http url in response
                            text = json.dumps(poll_data)
                            import re
                            urls = re.findall(r'https://[^\s"\']+\.mp4[^\s"\']*', text)
                            if urls:
                                agnes_video_url = urls[0]
                        
                        if agnes_video_url:
                            print(f"Found Agnes video URL: {agnes_video_url}")
                            break
                        
                        if status in ["failed", "error"]:
                            raise Exception(f"Agnes generation failed: {poll_data}")
                            
                except Exception as e:
                    print(f"Poll error {attempt}: {e}")
                    continue
            
            if not agnes_video_url:
                raise Exception("Agnes did not return video URL after polling")
            
            # Download Agnes video to our videos folder
            print(f"Downloading Agnes video from {agnes_video_url} to {video_path}")
            r = requests.get(agnes_video_url, stream=True, timeout=120)
            r.raise_for_status()
            with open(video_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Saved Agnes video to {video_path}, size {os.path.getsize(video_path)} bytes")
            
        except Exception as e:
            import traceback
            print(f"Agnes generation failed: {e}")
            print(traceback.format_exc())
            # Fallback to static if Agnes fails, so APK still gets a file
            try:
                import subprocess
                cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-c:v", "libx264", "-t", str(final_duration), "-pix_fmt", "yuv420p", "-vf", f"scale={width}:-2", video_path]
                subprocess.run(cmd, capture_output=True, timeout=30)
                if not os.path.exists(video_path):
                    shutil.copy(image_path, video_path)
            except:
                shutil.copy(image_path, video_path)

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
        "platform": platform,
        "width": width,
        "height": height,
        "num_frames": num_frames
    }
    HISTORY.append(entry)
    return entry
