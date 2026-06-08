"""Testes da API: endpoints simples (TestClient) e orquestração de jobs."""
import asyncio

import pytest
from fastapi.testclient import TestClient

import api


async def _noop_save(job):
    """Substitui save_job nos testes para não tocar o banco."""
    return None


# ── Endpoints simples ─────────────────────────────────────────────────────────

def test_list_jobs_empty():
    client = TestClient(api.app)
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json() == []


def test_get_job_not_found():
    client = TestClient(api.app)
    r = client.get("/api/jobs/inexistente")
    assert r.status_code == 404


def test_create_job_invalid_query_type():
    client = TestClient(api.app)
    r = client.post("/api/jobs", json={"url": "x", "query_type": "invalido"})
    assert r.status_code == 422  # validação do Pydantic


def test_create_job_save_failure_returns_json_error(monkeypatch):
    """Falha ao gravar no banco deve virar erro 500 em JSON com detail
    (e não o texto 'Internal Server Error' que quebrava o parse no frontend)."""
    async def failing_save(job):
        raise Exception("attempt to write a readonly database")

    monkeypatch.setattr(api, "save_job", failing_save)
    client = TestClient(api.app)
    r = client.post("/api/jobs", json={"url": "x"})
    assert r.status_code == 500
    body = r.json()  # precisa ser JSON válido
    assert "downloads" in body["detail"].lower()
    # o job não deve ter ficado registrado em memória após a falha
    assert api._jobs == {}


# ── Orquestração: _run_download_phase ─────────────────────────────────────────

async def test_download_phase_counts_results(monkeypatch, tmp_path):
    """Verifica a contagem done/skipped/failed e a propagação do erro."""
    from downloader import DownloadResult

    def fake_download(artist, title, dest, **kw):
        return {
            "ok": DownloadResult("done"),
            "exists": DownloadResult("skipped"),
            "fail": DownloadResult("failed", "Vídeo indisponível no YouTube"),
        }[title]

    monkeypatch.setattr(api, "download_track", fake_download)
    monkeypatch.setattr(api, "save_job", _noop_save)

    job = {
        "id": "j1",
        "done": 0, "skipped": 0, "failed_count": 0,
        "filename_template": "{artist} - {name}",
        "tracks": [
            {"artist": "a", "title": "ok", "status": "pending", "error": None},
            {"artist": "a", "title": "exists", "status": "pending", "error": None},
            {"artist": "a", "title": "fail", "status": "pending", "error": None},
        ],
    }
    api._jobs["j1"] = job
    api._cancel_events["j1"] = asyncio.Event()

    await api._run_download_phase(job, str(tmp_path))

    assert job["done"] == 3
    assert job["skipped"] == 1
    assert job["failed_count"] == 1
    assert job["status"] == "completed"

    by_title = {t["title"]: t["status"] for t in job["tracks"]}
    assert by_title == {"ok": "done", "exists": "skipped", "fail": "failed"}

    # a mensagem de erro deve ser propagada para a faixa que falhou
    failed_track = next(t for t in job["tracks"] if t["title"] == "fail")
    assert failed_track["error"] == "Vídeo indisponível no YouTube"


async def test_download_phase_respects_cancel(monkeypatch, tmp_path):
    """Se o cancel_event já está setado, todas as faixas viram cancelled."""
    from downloader import DownloadResult
    monkeypatch.setattr(api, "download_track", lambda *a, **k: DownloadResult("done"))
    monkeypatch.setattr(api, "save_job", _noop_save)

    job = {
        "id": "j2",
        "done": 0, "skipped": 0, "failed_count": 0,
        "filename_template": "{artist} - {name}",
        "tracks": [{"artist": "a", "title": "x", "status": "pending"}],
    }
    api._jobs["j2"] = job
    ev = asyncio.Event()
    ev.set()
    api._cancel_events["j2"] = ev

    await api._run_download_phase(job, str(tmp_path))

    assert job["status"] == "cancelled"
    assert job["tracks"][0]["status"] == "cancelled"


# ── Orquestração: _run_job (truncação por max_tracks) ─────────────────────────

async def test_run_job_truncates_to_max_tracks(monkeypatch, tmp_path):
    def fake_get(url, query_type):
        return ("MinhaLista", [{"artist": "a", "title": str(i)} for i in range(10)])

    from downloader import DownloadResult
    monkeypatch.setattr(api, "get_playlist_tracks", fake_get)
    monkeypatch.setattr(api, "download_track", lambda *a, **k: DownloadResult("done"))
    monkeypatch.setattr(api, "save_job", _noop_save)
    monkeypatch.setattr(api, "OUTPUT_DIR", str(tmp_path))

    job = {
        "id": "j3", "url": "qualquer", "query_type": "url",
        "max_tracks": 5,
        "done": 0, "skipped": 0, "failed_count": 0,
        "filename_template": "{artist} - {name}",
        "tracks": [], "status": "pending",
    }
    api._jobs["j3"] = job
    api._cancel_events["j3"] = asyncio.Event()

    await api._run_job("j3")

    assert job["total"] == 5
    assert job["truncated"] is True
    assert job["original_total"] == 10
    assert job["playlist_name"] == "MinhaLista"
    assert job["status"] == "completed"


async def test_run_job_handles_fetch_error(monkeypatch):
    def fake_get(url, query_type):
        raise ValueError("playlist não encontrada")

    monkeypatch.setattr(api, "get_playlist_tracks", fake_get)
    monkeypatch.setattr(api, "save_job", _noop_save)

    job = {
        "id": "j4", "url": "x", "query_type": "url",
        "status": "pending", "error": None, "tracks": [],
    }
    api._jobs["j4"] = job
    api._cancel_events["j4"] = asyncio.Event()

    await api._run_job("j4")

    assert job["status"] == "error"
    assert "não encontrada" in job["error"]
