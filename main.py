
"""
AppImgVid-backend2026 - 100% FREE - FIXED BLACK SCREEN
Render.com Free - Always returns valid MP4

Fix for black screen 0s:
1. Old code tried to download video from HF Space but saved 0 bytes on Render ephemeral storage
2. New code: ALWAYS creates valid MP4 locally with OpenCV as fallback, so timeline never 0
3. When HF Space with Wan 2.1 is awake, uses it. When sleeping, uses free Ken Burns animation

This is 100% free, no keys, works on Render free tier CPU.
"""

import os, uuid, shutil, asyncio, httpx
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fixed-backend")

app = FastAPI(title="AppImgVid-backend2026 FIXED", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = Path("/tmp/app2vid_fixed")
UPLOAD_DIR = BASE / "uploads"
VIDEO_DIR = BASE / "videos"
for d in [UPLOAD_DIR, VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")

FREE_SPACES = [
    "WanVideo/Wan2.1-I2V-14B-480P",
    "multimodalart/wan2-1-image-to-video",
]

def create_valid_mp4_from_image(image_path: Path, duration: int, resolution: str, motion_prompt: str, output_path: Path):
    """
    100% FREE fallback - Creates REAL valid MP4 from image with Ken Burns effect
    This guarantees Android ExoPlayer never gets black 0s video
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image

        # Resolution mapping
        if "1080" in resolution:
            w, h = 1280, 720
        elif "720" in resolution:
            w, h = 960, 540
        else:
            w, h = 640, 480  # 480p fastest for free tier

        # Load and resize image
        img = Image.open(image_path).convert("RGB")
        img = img.resize((w, h), Image.LANCZOS)
        img_np = np.array(img)
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Video writer - mp4v is Android compatible
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        fps = 8  # Wan 2.1 uses 8 fps, matches timeline
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        if not out.isOpened():
            # fallback codec
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        num_frames = max(24, duration * fps)
        
        # Parse motion_prompt for effect
        prompt_low = motion_prompt.lower()
        zoom_in = "zoom in" in prompt_low or "push in" in prompt_low or "smile" in prompt_low or "wind" not in prompt_low
        pan_left = "pan left" in prompt_low or "left" in prompt_low
        pan_right = "pan right" in prompt_low or "right" in prompt_low

        for i in range(num_frames):
            progress = i / num_frames
            
            # Ken Burns zoom effect - always visible motion
            if zoom_in:
                scale = 1.0 + progress * 0.3  # zoom 1.0 -> 1.3
            else:
                scale = 1.3 - progress * 0.3  # zoom out

            # Calculate crop for zoom
            h_crop = int(h / scale)
            w_crop = int(w / scale)
            
            # Pan effect
            if pan_left:
                x_offset = int((w - w_crop) * progress)
                y_offset = (h - h_crop) // 2
            elif pan_right:
                x_offset = int((w - w_crop) * (1 - progress))
                y_offset = (h - h_crop) // 2
            else:
                x_offset = (w - w_crop) // 2
                y_offset = (h - h_crop) // 2

            # Ensure bounds
            x_offset = max(0, min(x_offset, w - w_crop))
            y_offset = max(0, min(y_offset, h - h_crop))

            # Crop and resize back to full size
            cropped = img_np[y_offset:y_offset+h_crop, x_offset:x_offset+w_crop]
            if cropped.size == 0:
                cropped = img_np
            resized = cv2.resize(cropped, (w, h))

            # Add slight brightness variation for "animation" feel
            # This makes it not 100% static
            brightness = int(5 * np.sin(progress * 3.14 * 2))
            if brightness != 0:
                resized = cv2.add(resized, np.ones(resized.shape, dtype=np.uint8) * brightness)

            out.write(resized)

        out.release()
        logger.info(f"Created valid MP4: {output_path} - {num_frames} frames, {duration}s")
        return True

    except Exception as e:
        logger.exception(f"OpenCV creation failed: {e}")
        # Emergency fallback: create 1 frame video with imageio
        try:
            from PIL import Image
            import imageio.v2 as imageio
            img = Image.open(image_path).convert("RGB").resize((640, 480))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            writer = imageio.get_writer(str(output_path), fps=8, macro_block_size=1)
            for _ in range(duration * 8):
                writer.append_data(np.array(img))
            writer.close()
            return True
        except Exception as e2:
            logger.exception(f"Emergency fallback failed: {e2}")
            return False

async def try_wan_space(image_path: Path, prompt: str, neg_prompt: str, duration: int, resolution: str) -> Optional[Path]:
    """Try HF Space, return local video path if success, None if fail"""
    try:
        from gradio_client import Client, handle_file
        for space_id in FREE_SPACES:
            try:
                logger.info(f"Trying space {space_id}")
                client = Client(space_id)
                result = client.predict(
                    image=handle_file(str(image_path)),
                    prompt=prompt,
                    negative_prompt=neg_prompt,
                    api_name="/predict"
                )
                # result could be video path
                logger.info(f"Space result: {result}")
                if isinstance(result, str) and os.path.exists(result):
                    return Path(result)
                elif isinstance(result, str) and result.startswith("http"):
                    # download it
                    dest = VIDEO_DIR / f"{uuid.uuid4()}.mp4"
                    async with httpx.AsyncClient(timeout=120) as http_client:
                        r = await http_client.get(result, follow_redirects=True)
                        dest.write_bytes(r.content)
                        if dest.stat().st_size > 1000:
                            return dest
            except Exception as e:
                logger.warning(f"Space {space_id} failed: {e}")
                continue
        return None
    except Exception as e:
        logger.warning(f"Wan space attempt failed: {e}")
        return None

@app.get("/")
def root():
    return {"service": "AppImgVid-backend2026 FIXED", "black_screen_fix": True, "free": True}

@app.get("/health")
def health():
    return {"ok": True, "free": True, "fix": "OpenCV fallback ensures valid MP4"}

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
        # Save upload
        p1 = UPLOAD_DIR / f"{job_id}_1.jpg"
        with p1.open("wb") as f: shutil.copyfileobj(image1.file, f)

        try:
            duration_int = int(duration)
        except:
            duration_int = 5
        duration_int = max(3, min(20, duration_int))

        final_prompt = motion_prompt
        if camera_control == "static":
            final_prompt = f"{motion_prompt}, static camera"

        # Try real Wan 2.1 first
        wan_video_path = await try_wan_space(p1, final_prompt, negative_prompt, duration_int, resolution)
        
        output_path = VIDEO_DIR / f"{job_id}.mp4"
        
        if wan_video_path and wan_video_path.exists() and wan_video_path.stat().st_size > 5000:
            # Use Wan result
            shutil.copy(wan_video_path, output_path)
            logger.info(f"Using Wan 2.1 result: {output_path}")
        else:
            # 100% FREE FALLBACK - Always creates valid video, never black
            success = create_valid_mp4_from_image(p1, duration_int, resolution, final_prompt, output_path)
            if not success or not output_path.exists() or output_path.stat().st_size < 1000:
                raise Exception("Failed to create fallback video")

        # Build URL - Render provides external URL
        base = os.getenv("RENDER_EXTERNAL_URL") or f"https://{os.getenv('RENDER_SERVICE_NAME', 'appimgvid-backend2026')}.onrender.com"
        if not base.startswith("http"):
            base = f"https://{base}"
        # For local dev, if no env, use relative (Android will use full URL from response)
        video_url = f"{base}/videos/{output_path.name}"
        
        # Also verify file is valid
        size = output_path.stat().st_size
        logger.info(f"Returning video {video_url} size {size} bytes")

        return JSONResponse({
            "job_id": job_id,
            "video_url": video_url,
            "status": "done",
            "size": size,
            "duration": duration_int,
            "resolution": resolution,
            "note": "100% free - OpenCV fallback if Wan Space sleeping"
        })

    except Exception as e:
        logger.exception("generate failed")
        raise HTTPException(500, f"Generation failed: {str(e)}")

@app.get("/api/video/{filename}")
def get_video(filename: str):
    f = VIDEO_DIR / filename
    if not f.exists():
        raise HTTPException(404, "Video not found - Render free tier deletes on restart")
    return FileResponse(f, media_type="video/mp4", headers={"Accept-Ranges": "bytes"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
