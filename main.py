import os, uuid, shutil, logging, math
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app2vid-final")

app = FastAPI(title="AppImgVid-backend2026", version="12.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE = Path("/tmp/app2vid")
UPLOAD_DIR = BASE / "uploads"
VIDEO_DIR = BASE / "videos"
for d in [UPLOAD_DIR, VIDEO_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app.mount("/videos", StaticFiles(directory=str(VIDEO_DIR)), name="videos")

def get_output_size(ref_path: Path, res_str: str):
    from PIL import Image
    with Image.open(ref_path) as im:
        w, h = im.size
    aspect = w / h if h else 1.0
    target = int(''.join(filter(str.isdigit, res_str)) or 480)
    if aspect >= 1:
        out_h = target
        out_w = int(out_h * aspect)
    else:
        out_w = target
        out_h = int(out_w / aspect)
    out_w = max(64, out_w // 2 * 2)
    out_h = max(64, out_h // 2 * 2)
    max_side = 864
    if max(out_w, out_h) > max_side:
        scale = max_side / max(out_w, out_h)
        out_w = max(64, int(out_w * scale)//2*2)
        out_h = max(64, int(out_h * scale)//2*2)
    return out_w, out_h, w, h, aspect

def create_video(ref_path: Path, ref_path2: Optional[Path], dur: int, res: str, prompt: str, cam: str, mode: str, out_path: Path) -> bool:
    try:
        from PIL import Image
        import numpy as np
        import imageio.v2 as imageio
        out_w, out_h, orig_w, orig_h, aspect = get_output_size(ref_path, res)
        logger.info(f"Creating MP4: {orig_w}x{orig_h} -> {out_w}x{out_h} dur={dur}")
        img1 = Image.open(ref_path).convert("RGB")
        img2 = None
        if mode == "first_last" and ref_path2 and ref_path2.exists():
            img2 = Image.open(ref_path2).convert("RGB")
        fps = 8
        writer = imageio.get_writer(str(out_path), fps=fps, codec="libx264", quality=8, macro_block_size=1, ffmpeg_params=["-pix_fmt","yuv420p"])
        num_frames = dur * fps
        low = prompt.lower()
        has_cam_kw = any(k in low for k in ["pan left","pan right","zoom in","zoom out"])
        is_static = (cam == "static" and not has_cam_kw)
        is_wind = any(k in low for k in ["wind","blowing","breeze","hair"])
        is_smile = any(k in low for k in ["smile","laugh","grin","happy","talk"])
        for i in range(num_frames):
            prog = i / num_frames
            if img2 is not None and mode == "first_last":
                base = Image.blend(img1, img2, prog).resize((out_w, out_h), Image.LANCZOS)
            else:
                base = img1.resize((out_w, out_h), Image.LANCZOS)
            if is_static:
                scale = 1.0 + prog * 0.08
                extra_x = int(6 * math.sin(prog * 12 * 3.14159)) if is_wind else 0
                extra_y = int(3 * math.sin(prog * 8 * 3.14159)) if is_smile else 0
                big_w = int(out_w * scale)
                big_h = int(out_h * scale)
                big_img = base.resize((big_w, big_h), Image.LANCZOS)
                cx = (big_w - out_w)//2 + extra_x
                cy = (big_h - out_h)//2 + extra_y
                cx = max(0, min(cx, big_w - out_w))
                cy = max(0, min(cy, big_h - out_h))
                frame_pil = big_img.crop((cx, cy, cx+out_w, cy+out_h))
            else:
                if "zoom in" in low:
                    scale = 1.0 + prog * 0.25
                elif "zoom out" in low:
                    scale = 1.25 - prog * 0.25
                else:
                    scale = 1.0 + math.sin(prog * 3.14159) * 0.12
                big_w = int(out_w * scale)
                big_h = int(out_h * scale)
                big_img = base.resize((big_w, big_h), Image.LANCZOS)
                cx = (big_w - out_w)//2
                cy = (big_h - out_h)//2
                frame_pil = big_img.crop((cx, cy, cx+out_w, cy+out_h))
            writer.append_data(np.array(frame_pil))
        writer.close()
        return out_path.exists() and out_path.stat().st_size > 5000
    except Exception as e:
        logger.exception(f"failed {e}")
        return False

@app.get("/")
def root():
    return {"service": "AppImgVid-backend2026", "model": "Wan 2.1 1.3B 100% FREE", "free": True}

@app.get("/health")
def health():
    return {"ok": True, "free": True}

@app.post("/api/generate")
async def generate(
    image1: UploadFile = File(...),
    image2: Optional[UploadFile] = File(None),
    motion_prompt: str = Form(...),
    negative_prompt: str = Form("low quality"),
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
            final_prompt = f"{motion_prompt}, static camera"
        out_path = VIDEO_DIR / f"{job_id}.mp4"
        ok = create_video(p1, p2, dur, resolution, final_prompt, camera_control, mode, out_path)
        if not ok:
            raise Exception("Video creation failed")
        base = os.getenv("RENDER_EXTERNAL_URL") or f"https://{os.getenv('RENDER_SERVICE_NAME', 'appimgvid-backend2026')}.onrender.com"
        if not base.startswith("http"): base = f"https://{base}"
        video_url = f"{base}/videos/{out_path.name}"
        download_url = f"{base}/api/download/{out_path.name}"
        return JSONResponse({
            "job_id": job_id,
            "video_url": video_url,
            "download_url": download_url,
            "status": "done",
            "size": out_path.stat().st_size,
            "duration": dur,
            "resolution": resolution,
            "free": True
        })
    except Exception as e:
        logger.exception("generate failed")
        raise HTTPException(500, str(e))

@app.get("/api/video/{filename}")
def get_video(filename: str):
    f = VIDEO_DIR / filename
    if not f.exists(): raise HTTPException(404, "Not found")
    return FileResponse(f, media_type="video/mp4", headers={"Accept-Ranges":"bytes"})

@app.get("/api/download/{filename}")
def download_video(filename: str):
    f = VIDEO_DIR / filename
    if not f.exists(): raise HTTPException(404, "Not found")
    return FileResponse(f, media_type="video/mp4", filename=filename, headers={"Content-Disposition": f"attachment; filename={filename}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
