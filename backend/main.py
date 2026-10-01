import asyncio
import os
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── ספריית הורדות זמנית ──────────────────────────────────────────────────────
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="YouTube Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── מודלים ───────────────────────────────────────────────────────────────────
class DownloadRequest(BaseModel):
    youtube_url: str
    format_type: str = "mp4"
    base_url: str  # כתובת אתר ה-converter החיצוני


class JobStatus(BaseModel):
    job_id: str
    status: str          # "pending" | "running" | "done" | "error"
    message: str = ""
    filename: str = ""


# ── מצב עבודות פנימי (בזיכרון, מספיק לשרת יחיד) ─────────────────────────
jobs: dict[str, JobStatus] = {}


# ── לוגיקת ההורדה (async wrapper ל-Playwright sync) ─────────────────────────
async def _run_download(job_id: str, base_url: str, youtube_url: str, format_type: str):
    jobs[job_id].status = "running"
    jobs[job_id].message = "מחלץ מזהה סרטון..."

    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
    if not video_id_match:
        jobs[job_id].status = "error"
        jobs[job_id].message = "לא נמצא מזהה סרטון תקין בקישור."
        return

    video_id = video_id_match.group(1)
    target_url = f"{base_url}/#{video_id}/{format_type}"
    jobs[job_id].message = f"מנווט לאתר ההמרה..."

    # הרצת Playwright בthread נפרד כדי לא לחסום את event-loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _playwright_download, job_id, target_url, format_type)

    if result["ok"]:
        jobs[job_id].status = "done"
        jobs[job_id].filename = result["filename"]
        jobs[job_id].message = "ההורדה הושלמה בהצלחה!"
    else:
        jobs[job_id].status = "error"
        jobs[job_id].message = result["error"]


def _playwright_download(job_id: str, target_url: str, format_type: str) -> dict:
    """רץ בthread נפרד — מריץ Playwright sync."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            jobs[job_id].message = "טוען את אתר ההמרה..."
            page.goto(target_url, wait_until="networkidle")

            jobs[job_id].message = "ממתין לסיום ההמרה (עד 3 דקות)..."

            download_btn = page.locator("button.download")
            download_btn.wait_for(state="visible", timeout=180_000)

            jobs[job_id].message = "ההמרה הסתיימה, מוריד קובץ..."

            with page.expect_download(timeout=120_000) as dl_info:
                download_btn.click()

            dl = dl_info.value
            suggested = dl.suggested_filename or f"video_{job_id}.{format_type}"
            save_path = DOWNLOADS_DIR / suggested
            dl.save_as(str(save_path))
            browser.close()

        return {"ok": True, "filename": suggested}

    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


# ── API Routes ────────────────────────────────────────────────────────────────
@app.post("/api/download", response_model=JobStatus)
async def start_download(req: DownloadRequest):
    job_id = str(uuid.uuid4())
    jobs[job_id] = JobStatus(job_id=job_id, status="pending", message="ממתין להתחלה...")
    asyncio.create_task(_run_download(job_id, req.base_url, req.youtube_url, req.format_type))
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


# ── Serve Frontend ────────────────────────────────────────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
