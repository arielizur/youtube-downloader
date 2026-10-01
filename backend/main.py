import asyncio
import os
import uuid
from pathlib import Path
import yt_dlp

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
    base_url: str = "" # לא בשימוש יותר אבל נשאר לתאימות אם ה-JS עדיין שולח

class JobStatus(BaseModel):
    job_id: str
    status: str
    message: str = ""
    filename: str = ""

jobs: dict[str, JobStatus] = {}

def _yt_dlp_download(job_id: str, url: str, format_type: str) -> dict:
    try:
        # הגדרת נתיב שמירה לקובץ
        outtmpl = str(DOWNLOADS_DIR / f'%(title)s_{job_id}.%(ext)s')
        
        ydl_opts = {
            'outtmpl': outtmpl,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        
        if format_type == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else: # mp4
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            })
        jobs[job_id].message = "מוריד קובץ ישירות מיוטיוב..."
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # איתור השם הסופי של הקובץ שנוצר
            if format_type == 'mp3':
                filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            else:
                filename = ydl.prepare_filename(info)
                
        filename_only = os.path.basename(filename)
        return {"ok": True, "filename": filename_only}
        
    except Exception as e:
        return {"ok": False, "error": str(e)}
        
async def _run_download(job_id: str, youtube_url: str, format_type: str):
    jobs[job_id].status = "running"
    jobs[job_id].message = "מעבד את הקישור..."

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _yt_dlp_download, job_id, youtube_url, format_type)

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
