import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import init_db, load_jobs, save_job
from downloader import download_track, DEFAULT_TEMPLATE
from spotify_client import get_playlist_tracks, _get_client

OUTPUT_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
MAX_TRACKS = int(os.getenv("MAX_TRACKS_PER_PLAYLIST", "50"))

_jobs: dict[str, dict] = {}
_cancel_events: dict[str, asyncio.Event] = {}


@asynccontextmanager
async def lifespan(app):
    await init_db()
    for job in await load_jobs():
        if job["status"] in ("pending", "fetching", "downloading"):
            job["status"] = "cancelled"
            for track in job.get("tracks", []):
                if track["status"] in ("pending", "downloading"):
                    track["status"] = "cancelled"
        _jobs[job["id"]] = job
        _cancel_events[job["id"]] = asyncio.Event()
    yield


app = FastAPI(title="SpotDownload API", lifespan=lifespan)


# ── Spotify status ────────────────────────────────────────────────────────────

@app.get("/api/spotify/status")
async def spotify_status():
    try:
        await asyncio.to_thread(_get_client)
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.post("/api/spotify/disconnect")
async def spotify_disconnect():
    import spotify_client
    spotify_client._client = None
    return {"connected": False}


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    url: str
    filename_template: str = DEFAULT_TEMPLATE


@app.post("/api/jobs")
async def create_job(req: JobRequest):
    job_id = str(uuid.uuid4())[:8]
    job = {
        "id": job_id,
        "url": req.url,
        "status": "pending",
        "total": 0,
        "done": 0,
        "skipped": 0,
        "failed_count": 0,
        "playlist_name": None,
        "tracks": [],
        "error": None,
        "truncated": False,
        "original_total": 0,
        "max_tracks": MAX_TRACKS,
        "filename_template": req.filename_template,
        "created_at": datetime.now().isoformat(),
    }
    _jobs[job_id] = job
    _cancel_events[job_id] = asyncio.Event()
    await save_job(job)
    asyncio.create_task(_run_job(job_id))
    return job


@app.get("/api/jobs")
async def list_jobs():
    return list(reversed(list(_jobs.values())))


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _jobs[job_id]


@app.delete("/api/jobs")
async def clear_history():
    """Remove do histórico todos os jobs finalizados."""
    finished = [
        jid for jid, j in _jobs.items()
        if j["status"] in ("completed", "cancelled", "error")
    ]
    for jid in finished:
        del _jobs[jid]
        del _cancel_events[jid]

    async with __import__("aiosqlite").connect(__import__("db").DB_PATH) as db:
        await db.execute(
            f"DELETE FROM jobs WHERE id IN ({','.join('?' * len(finished))})",
            finished,
        )
        await db.commit()

    return {"removed": len(finished)}


@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["status"] not in ("fetching", "downloading"):
        raise HTTPException(status_code=400, detail="Job não está em andamento")
    _cancel_events[job_id].set()
    return {"ok": True}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    if job["status"] not in ("completed", "cancelled", "error"):
        raise HTTPException(status_code=400, detail="Job ainda em andamento")

    retryable = [t for t in job["tracks"] if t["status"] in ("failed", "cancelled")]
    if not retryable:
        raise HTTPException(status_code=400, detail="Sem faixas para re-tentar")

    job["failed_count"] -= sum(1 for t in retryable if t["status"] == "failed")
    job["done"] -= len(retryable)
    for t in retryable:
        t["status"] = "pending"
    job["status"] = "downloading"

    _cancel_events[job_id] = asyncio.Event()
    dest_dir = str(Path(OUTPUT_DIR) / (job["playlist_name"] or ""))
    asyncio.create_task(_run_download_phase(job, dest_dir))
    await save_job(job)
    return job


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    async def stream():
        while True:
            job = _jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break
            yield f"data: {json.dumps(job, ensure_ascii=False)}\n\n"
            if job["status"] in ("completed", "error", "cancelled"):
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Job runner ────────────────────────────────────────────────────────────────

async def _run_job(job_id: str):
    job = _jobs[job_id]
    try:
        job["status"] = "fetching"
        await save_job(job)
        playlist_name, all_tracks = await asyncio.to_thread(get_playlist_tracks, job["url"])
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        await save_job(job)
        return

    dest_dir = str(Path(OUTPUT_DIR) / playlist_name)
    Path(dest_dir).mkdir(parents=True, exist_ok=True)

    tracks = all_tracks[:MAX_TRACKS]
    job.update({
        "total": len(tracks),
        "truncated": len(all_tracks) > MAX_TRACKS,
        "original_total": len(all_tracks),
        "playlist_name": playlist_name,
        "status": "downloading",
        "tracks": [
            {
                "artist": t["artist"],
                "title": t["title"],
                "album": t.get("album"),
                "track_number": t.get("track_number"),
                "cover_url": t.get("cover_url"),
                "release_date": t.get("release_date"),
                "status": "pending",
            }
            for t in tracks
        ],
    })
    await save_job(job)
    await _run_download_phase(job, dest_dir)


async def _run_download_phase(job: dict, dest_dir: str):
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(3)
    cancel_event = _cancel_events[job["id"]]
    pending = [t for t in job["tracks"] if t["status"] == "pending"]

    async def download_one(track_state: dict):
        if cancel_event.is_set():
            track_state["status"] = "cancelled"
            job["done"] += 1
            return

        async with sem:
            if cancel_event.is_set():
                track_state["status"] = "cancelled"
                job["done"] += 1
                return

            track_state["status"] = "downloading"
            result = await asyncio.to_thread(
                download_track,
                track_state["artist"],
                track_state["title"],
                dest_dir,
                album=track_state.get("album"),
                track_number=track_state.get("track_number"),
                cover_url=track_state.get("cover_url"),
                release_date=track_state.get("release_date"),
                filename_template=job.get("filename_template", DEFAULT_TEMPLATE),
            )

        if result is True:
            track_state["status"] = "done"
            job["done"] += 1
        elif result is None:
            track_state["status"] = "skipped"
            job["done"] += 1
            job["skipped"] += 1
        else:
            track_state["status"] = "failed"
            job["done"] += 1
            job["failed_count"] += 1

        await save_job(job)

    await asyncio.gather(*[download_one(t) for t in pending])
    job["status"] = "cancelled" if cancel_event.is_set() else "completed"
    await save_job(job)


# Must be last
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
