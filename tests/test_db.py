"""Testes de persistência (SQLite) com banco temporário."""
import db


async def test_db_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_db_dir", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))

    await db.init_db()

    job = {
        "id": "abc123",
        "created_at": "2024-01-01T00:00:00",
        "status": "completed",
        "playlist_name": "Minha Lista",
        "tracks": [{"artist": "A", "title": "T", "status": "done"}],
    }
    await db.save_job(job)

    loaded = await db.load_jobs()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "abc123"
    assert loaded[0]["playlist_name"] == "Minha Lista"
    assert loaded[0]["tracks"][0]["title"] == "T"


async def test_db_save_replaces_existing(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_db_dir", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))

    await db.init_db()
    job = {"id": "x", "created_at": "2024-01-01", "status": "pending"}
    await db.save_job(job)

    job["status"] = "completed"
    await db.save_job(job)  # mesmo id → substitui

    loaded = await db.load_jobs()
    assert len(loaded) == 1
    assert loaded[0]["status"] == "completed"


async def test_db_load_orders_by_created_at(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "_db_dir", str(tmp_path))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))

    await db.init_db()
    await db.save_job({"id": "b", "created_at": "2024-02-01", "status": "x"})
    await db.save_job({"id": "a", "created_at": "2024-01-01", "status": "x"})

    loaded = await db.load_jobs()
    assert [j["id"] for j in loaded] == ["a", "b"]  # ordem cronológica ascendente
