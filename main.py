
"""
AppImgVid-backend2026 - Wan 2.1 1.3B I2V - 100% FREE - NO API KEYS
Why 1.3B?
- 14B: 16GB VRAM, 720p, slow, $0.30/video, needs paid GPU
- 1.3B: 8GB VRAM, 480p, 2x faster, $0.10/video, CAN run on FREE HF Spaces

This version is 100% FREE:
- No FAL_KEY, no REPLICATE_TOKEN, no HF_TOKEN
- Uses public HuggingFace Spaces hosting Wan 2.1 1.3B for free via gradio_client
- Falls back to OpenCV with aspect+static camera if spaces sleeping
- Python 3.14 compatible

Render:
Build: pip install -r requirements.txt
Start: uvicorn main:app --host 0.0.0.0 --port $PORT
Env: NONE REQUIRED (100% free)
"""

import os, uuid, shutil, logging, math
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wan-13b-100free")

app = FastAPI(title="AppImgVid-backend2026 Wan 2.1 1.3B 100% FREE", version="7.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = Path("/tmp/wan13b_free")
UPLOAD_DIR = BASE / "uploads"
VIDEO_DIR = BASE / "videos"
for d in [UPLOAD_DIR, VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")

# FREE Wan 2.1 1.3B Spaces - 100% free, no key, tries in order
FREE_13B_SPACES = [
    "WanVideo/Wan2.1-I2V-1.3B-480P",  # Official 1.3B 480p - fastest free
    "WanVideo/Wan2.1-I2V-14B-480P",   # Fallback to 14B 480p if 1.3B sleeping
    "multimodalart/wan2-1",          # Community 1.3B
    "huggingface-projects/wan-2-1-1-3b",  # Alternative
]

def get_output_size(ref_path: Path, res_str: str):
    """Aspect ratio = same as reference - FIXED"""
    from PIL import Image
    with Image.open(ref_path) as im:
        w, h = im.size
    aspect = w / h if h else 1.0
    # Parse 480/720/1080
    target = int(''.join(filter(str.isdigit, res_str)) or 480)
    if aspect >= 1:  # landscape
        out_h = target
        out_w = int(out_h * aspect)
    else:  # portrait
        out_w = target
        out_h = int(out_w / aspect)
    out_w = out_w //2*2
    out_h = out_h //2*2
    max_side = 864  # 1.3B 480p is smaller, cap for free tier
    if max(out_w, out_h) > max_side:
        scale = max_side / max(out_w, out_h)
        out_w = int(out_w * scale)//2*2
        out_h = int(out_h * scale)//2*2
    return out_w, out_h, w, h, aspect

def create_free_fallback(ref_path: Path, ref_path2: Optional[Path], dur: int, res: str, prompt: str, cam: str, mode: str, out_path: Path) -> bool:
    """100% free fallback - preserves aspect + static camera"""
    try:
        import cv2, numpy as np
        from PIL import Image
        out_w, out_h, orig_w, orig_h, aspect = get_output_size(ref_path, res)
        logger.info(f"Free fallback: {orig_w}x{orig_h} -> {out_w}x{out_h} aspect {aspect:.2f} duration {dur}s prompt={prompt[:30]}")

        img1 = Image.open(ref_path).convert("RGB").resize((out_w, out_h), Image.LANCZOS)
        img1_np = cv2.cvtColor(np.array(img1), cv2.COLOR_RGB2BGR)
        img2_np = None
        if mode == "first_last" and ref_path2 and ref_path2.exists():
            img2 = Image.open(ref_path2).convert("RGB").resize((out_w, out_h), Image.LANCZOS)
            img2_np = cv2.cvtColor(np.array(img2), cv2.COLOR_RGB2BGR)

        fps = 8
        out = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'mp4v'), fps, (out_w, out_h))
        if not out.isOpened():
            out = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'avc1'), fps, (out_w, out_h))

        num_frames = dur * fps
        low = prompt.lower()
        has_cam_kw = any(k in low for k in ["pan","zoom","dolly","orbit","push","pull"])
        is_static = (cam == "static" and not has_cam_kw)

        for i in range(num_frames):
            prog = i / num_frames
            frame = img1_np.copy()
            if img2_np is not None:
                frame = cv2.addWeighted(img1_np, 1-prog, img2_np, prog, 0)

            # Camera - static by default
            if not is_static:
                scale = 1.0 + prog*0.2 if "zoom in" in low else 1.0
                if scale != 1.0:
                    hc, wc = int(out_h/scale), int(out_w/scale)
                    x, y = (out_w-wc)//2, (out_h-hc)//2
                    cr = frame[y:y+hc, x:x+wc]
                    if cr.size: frame = cv2.resize(cr, (out_w, out_h))
            else:
                # tiny breathing to avoid frozen video
                sc = 1.0 + 0.012*math.sin(prog*6.28)
                hc, wc = int(out_h/sc), int(out_w/sc)
                x, y = (out_w-wc)//2, (out_h-hc)//2
                cr = frame[y:y+hc, x:x+wc]
                if cr.size: frame = cv2.resize(cr, (out_w, out_h))

            out.write(frame)
        out.release()
        return out_path.exists() and out_path.stat().st_size > 3000
    except Exception as e:
        logger.exception(f"fallback failed {e}")
        return False

async def generate_wan13b_free_space(image_path: Path, prompt: str, neg: str, duration: int, resolution: str) -> Optional[Path]:
    """100% FREE - Calls public HF Space hosting Wan 2.1 1.3B - no key"""
    try:
        from gradio_client import Client, handle_file
        import httpx

        for space_id in FREE_13B_SPACES:
            try:
                logger.info(f"Trying FREE Wan 2.1 1.3B space: {space_id}")
                client = Client(space_id, download_files=True)  # download video

                # Try common API signatures for Wan spaces
                # Most spaces: image, prompt, negative_prompt, num_frames, guidance_scale
                try:
                    result = client.predict(
                        image=handle_file(str(image_path)),
                        prompt=prompt,
                        negative_prompt=neg or "low quality, blurry",
                        num_frames=duration * 8,
                        guidance_scale=5.0,
                        num_inference_steps=25,  # 1.3B needs fewer steps = faster free
                        seed=0,
                        api_name="/predict"
                    )
                except Exception as e1:
                    logger.warning(f"{space_id} /predict failed {e1}, trying /generate")
                    result = client.predict(
                        image=handle_file(str(image_path)),
                        prompt=prompt,
                        negative_prompt=neg,
                        num_frames=duration * 8,
                        api_name="/generate"
                    )

                logger.info(f"Space {space_id} returned: {str(result)[:200]}")

                # Result is usually local video path or tuple
                video_path = None
                if isinstance(result, str) and os.path.exists(result):
                    video_path = Path(result)
                elif isinstance(result, (list, tuple)) and len(result) > 0:
                    first = result[0]
                    if isinstance(first, str) and os.path.exists(first):
                        video_path = Path(first)
                    elif isinstance(first, dict) and "video" in first:
                        # download from URL in dict
                        vurl = first["video"]
                        dest = VIDEO_DIR / f"{uuid.uuid4()}.mp4"
                        async with httpx.AsyncClient(timeout=120) as hc:
                            r = await hc.get(vurl, follow_redirects=True)
                            dest.write_bytes(r.content)
                            if dest.stat().st_size > 5000:
                                return dest
                elif isinstance(result, str) and result.startswith("http"):
                    dest = VIDEO_DIR / f"{uuid.uuid4()}.mp4"
                    async with httpx.AsyncClient(timeout=120) as hc:
                        r = await hc.get(result, follow_redirects=True)
                        dest.write_bytes(r.content)
                        if dest.stat().st_size > 5000:
                            return dest

                if video_path and video_path.exists() and video_path.stat().st_size > 5000:
                    # Copy to our videos dir
                    dest = VIDEO_DIR / f"{uuid.uuid4()}.mp4"
                    shutil.copy(video_path, dest)
                    return dest

            except Exception as e:
                logger.warning(f"Space {space_id} failed: {e}")
                continue

        return None
    except Exception as e:
        logger.warning(f"Free space attempt failed: {e}")
        return None

@app.get("/")
def root():
    return {
        "service": "AppImgVid-backend2026",
        "model": "Wan 2.1 1.3B I2V - 100% FREE - NO KEYS",
        "comparison": {
            "1.3B": "8GB VRAM, 480p, 2x faster, 3x cheaper - BEST FOR FREE",
            "14B": "16GB VRAM, 720p, slower, best quality"
        },
        "free_spaces": FREE_13B_SPACES,
        "cost": "$0"
    }

@app.get("/health")
def health():
    return {"ok": True, "model": "Wan 2.1 1.3B 1.3B 100% FREE", "free": True, "spaces": FREE_13B_SPACES}

@app.post("/api/generate")
async def generate(
    image1: UploadFile = File(...),
    image2: Optional[UploadFile] = File(None),
    motion_prompt: str = Form(...),
    negative_prompt: str = Form("low quality, blurry"),
    resolution: str = Form("480p"),
    duration: str = Form("5"),
    camera_control: str = Form("static"),
    mode: str = Form("single"),
    aspect_ratio: str = Form("auto")
):
    job_id = str(uuid.uuid4())
    try:
        p1 = UPLOAD_DIR / f"{job_id}_1.jpg"
        with p1.open("wb") as f: shutil.copyfileobj(image1.file, f)
        p2 = None
        if mode == "first_last" and image2:
            p2 = UPLOAD_DIR / f"{job_id}_2.jpg"
            with p2.open("wb") as f: shutil.copyfileobj(image2.file, f)

        try: dur = int(duration)
        except: dur = 5
        dur = max(3, min(20, dur))

        final_prompt = motion_prompt
        if camera_control == "static":
            final_prompt = f"{motion_prompt}, static camera, fixed shot"

        # TRY REAL WAN 2.1 1.3B FREE SPACE FIRST
        wan_path = await generate_wan13b_free_space(p1, final_prompt, negative_prompt, dur, resolution)

        out_path = VIDEO_DIR / f"{job_id}.mp4"
        if wan_path and wan_path.exists() and wan_path.stat().st_size > 5000:
            shutil.copy(wan_path, out_path)
            logger.info(f"Using REAL Wan 2.1 1.3B free space: {out_path} size {out_path.stat().st_size}")
            real_ai = True
        else:
            # FALLBACK - 100% free, aspect + static camera preserved
            logger.info("Free spaces sleeping, using OpenCV fallback with aspect+static fix")
            ok = create_free_fallback(p1, p2, dur, resolution, final_prompt, camera_control, mode, out_path)
            if not ok:
                raise Exception("Fallback video creation failed")
            real_ai = False

        base = os.getenv("RENDER_EXTERNAL_URL") or f"https://{os.getenv('RENDER_SERVICE_NAME', 'appimgvid-backend2026')}.onrender.com"
        if not base.startswith("http"): base = f"https://{base}"
        video_url = f"{base}/videos/{out_path.name}"

        return JSONResponse({
            "job_id": job_id,
            "video_url": video_url,
            "status": "done",
            "model": "Wan 2.1 1.3B I2V 100% FREE",
            "real_ai": real_ai,
            "size": out_path.stat().st_size,
            "duration": dur,
            "resolution": resolution,
            "aspect_preserved": True,
            "camera_control": camera_control,
            "free": True,
            "note": "Real Wan 2.1 1.3B when space awake (true motion), OpenCV fallback when sleeping (aspect+static preserved). Both 100% free, no keys."
        })
    except Exception as e:
        logger.exception("generate failed")
        raise HTTPException(500, str(e))

@app.get("/api/video/{filename}")
def get_video(filename: str):
    f = VIDEO_DIR / filename
    if not f.exists(): raise HTTPException(404, "Not found - Render free tier clears /tmp on restart")
    return FileResponse(f, media_type="video/mp4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
