import asyncio
import os
import re
import uuid
import time
from pathlib import Path

# ספריה המזייפת טביעת אצבע של כרום כדי לעקוף את חסימות Cloudflare
from curl_cffi import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="YouTube Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    youtube_url: str
    format_type: str = "mp4"
    base_url: str = ""

class JobStatus(BaseModel):
    job_id: str
    status: str
    message: str = ""
    filename: str = ""

jobs: dict[str, JobStatus] = {}

def _download_from_worker(job_id: str, youtube_url: str, format_type: str) -> dict:
    try:
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
        if not video_id_match:
            return {"ok": False, "error": "Invalid YouTube URL"}
        video_id = video_id_match.group(1)

        url = f"https://fancy-sea-5d3d.holy-breeze-fec5.workers.dev/?m=i&v={video_id}&f={format_type}&_={int(time.time()*1000)}"
        headers = {
            "Origin": "https://convertytmp3.org",
            "Referer": "https://convertytmp3.org/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        jobs[job_id].message = "מתחבר לשרתי ההמרה הסודיים..."
        # השורה הזו (impersonate="chrome120") היא פריצת הדרך!
        r = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
        
        if r.status_code != 200:
            return {"ok": False, "error": f"Cloudflare block or server error (HTTP {r.status_code})"}
            
        data = r.json()
        if data.get("error", 0) > 0:
            return {"ok": False, "error": f"Server error: {data.get('error')}"}
            
        progress_url = data.get("progressURL")
        download_url = data.get("downloadURL")
        title = data.get("title", f"video_{job_id}")
        
        for _ in range(40):
            jobs[job_id].message = f"ממיר את הסרטון: {title[:25]}..."
            time.sleep(3)
            pr = requests.get(f"{progress_url}&_={int(time.time()*1000)}", headers=headers, impersonate="chrome120", timeout=10)
            pdata = pr.json()
            if pdata.get("progress") == 3:
                break
        
        jobs[job_id].message = "מוריד את הקובץ המוכן לשרת שלנו..."
        
        r_down = requests.get(download_url, headers=headers, impersonate="chrome120", stream=True)
        if r_down.status_code != 200:
            return {"ok": False, "error": "Failed to download file."}
            
        cd = r_down.headers.get('Content-Disposition', '')
        fname_match = re.search(r'filename="([^"]+)"', cd)
        if fname_match:
            filename = fname_match.group(1)
        else:
            filename = f"{title}.{format_type}"
            
        filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in " .-_()א-ת"]).rstrip()
        
        save_path = DOWNLOADS_DIR / filename
        with open(save_path, 'wb') as f:
            for chunk in r_down.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        return {"ok": True, "filename": filename}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def _run_download(job_id: str, youtube_url: str, format_type: str):
    jobs[job_id].status = "running"
    jobs[job_id].message = "מתחיל תהליך..."
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _download_from_worker, job_id, youtube_url, format_type)

    if result["ok"]:
        jobs[job_id].status = "done"
        jobs[job_id].filename = result["filename"]
        jobs[job_id].message = "ההורדה הושלמה בהצלחה!"
    else:
        jobs[job_id].status = "error"
        jobs[job_id].message = result["error"]

@app.post("/api/download", response_model=JobStatus)
async def start_download(req: DownloadRequest):
    job_id = str(uuid.uuid4())
    jobs[job_id] = JobStatus(job_id=job_id, status="pending", message="ממתין להתחלה...")
    asyncio.create_task(_run_download(job_id, req.youtube_url, req.format_type))
    return jobs[job_id]

@app.get("/api/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="עבודה לא נמצאה")
    return jobs[job_id]

@app.get("/api/file/{job_id}")
async def get_file(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="עבודה לא נמצאה")
    job = jobs[job_id]
    if job.status != "done" or not job.filename:
        raise HTTPException(status_code=400, detail="הקובץ עדיין לא מוכן")
    file_path = DOWNLOADS_DIR / job.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="הקובץ לא נמצא בשרת")
    return FileResponse(
        path=str(file_path),
        filename=job.filename,
        media_type="application/octet-stream",
    )

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
