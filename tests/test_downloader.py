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
