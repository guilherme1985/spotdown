"""Testes das funções puras de nomeação de arquivo do downloader."""
import downloader


def test_apply_template_default():
    out = downloader._apply_template(
        "{artist} - {name}", "The Weeknd", "Blinding Lights", None, None, None
    )
    assert out == "The Weeknd - Blinding Lights"


def test_apply_template_number_padded():
    out = downloader._apply_template(
        "{number} - {name}", "A", "Song", "Album", 3, "2020"
    )
    assert out == "03 - Song"


def test_apply_template_all_variables():
    out = downloader._apply_template(
        "{number} {artist} {name} {album} {releaseDate}",
        "A", "S", "Alb", 1, "2020",
    )
    assert out == "01 A S Alb 2020"


def test_apply_template_strips_invalid_chars():
    out = downloader._apply_template(
        "{artist} - {name}", "AC/DC", "T:N*T?", None, None, None
    )
    # caracteres inválidos de nome de arquivo são removidos
    assert "/" not in out
    assert ":" not in out
    assert "*" not in out
    assert "?" not in out


def test_apply_template_fallback_when_empty():
    # template que resolve para vazio cai no fallback "artist - title"
    out = downloader._apply_template("{album}", "Artist", "Title", None, None, None)
    assert out == "Artist - Title"


def test_apply_template_missing_number():
    # sem track_number, {number} vira string vazia
    out = downloader._apply_template("{number}{name}", "A", "Song", None, None, None)
    assert out == "Song"


def test_safe_name_removes_all_invalid():
    assert downloader._safe_name('a/b\\c:d*e?f"g<h>i|j') == "abcdefghij"


def test_safe_name_trims_whitespace():
    assert downloader._safe_name("  hello  ") == "hello"


# ── Diagnóstico de falhas ─────────────────────────────────────────────────────

def test_humanize_error_video_unavailable():
    err = downloader._humanize_error(Exception("ERROR: Video unavailable"))
    assert err == "Vídeo indisponível no YouTube"


def test_humanize_error_private_video():
    assert downloader._humanize_error(Exception("Private video")) == "Vídeo privado"


def test_humanize_error_age_restricted():
    err = downloader._humanize_error(Exception("Sign in to confirm your age"))
    assert err == "Vídeo com restrição de idade"


def test_humanize_error_connection():
    assert downloader._humanize_error(Exception("Connection timed out")) == "Falha de conexão"


def test_humanize_error_strips_ansi_and_prefix():
    raw = Exception("\x1b[0;31mERROR:\x1b[0m algo deu errado")
    assert downloader._humanize_error(raw) == "algo deu errado"


def test_humanize_error_truncates_long_message():
    long = "x" * 500
    assert len(downloader._humanize_error(Exception(long))) == 200


def test_humanize_error_empty():
    assert downloader._humanize_error(Exception("")) == "Erro desconhecido"


def test_download_track_skips_existing(tmp_path):
    from downloader import DownloadResult
    # cria o arquivo de saída esperado para simular "já existe"
    existing = tmp_path / "The Weeknd - Blinding Lights.mp3"
    existing.write_text("fake")
    result = downloader.download_track(
        "The Weeknd", "Blinding Lights", str(tmp_path)
    )
    assert result == DownloadResult("skipped")


def test_download_track_failed_when_no_file(monkeypatch, tmp_path):
    """Se o yt-dlp termina sem erro mas não cria o arquivo, é falha diagnosticada."""
    from downloader import DownloadResult

    class FakeYDL:
        def __init__(self, opts): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def download(self, queries): pass  # não cria arquivo

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    result = downloader.download_track("A", "Inexistente", str(tmp_path))
    assert result.status == "failed"
    assert result.error == "Nenhum resultado encontrado no YouTube"
