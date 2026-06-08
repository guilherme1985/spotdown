import os
import re
import urllib.request
from typing import NamedTuple

import yt_dlp
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, TRCK
from mutagen.mp3 import MP3

DEFAULT_TEMPLATE = "{artist} - {name}"


class DownloadResult(NamedTuple):
    status: str                 # "done" | "skipped" | "failed"
    error: str | None = None    # mensagem amigável quando status == "failed"


def download_track(
    artist: str,
    title: str,
    output_dir: str,
    *,
    album: str | None = None,
    track_number: int | None = None,
    cover_url: str | None = None,
    release_date: str | None = None,
    filename_template: str = DEFAULT_TEMPLATE,
) -> DownloadResult:
    """Busca no YouTube e baixa o áudio como MP3.

    Retorna um DownloadResult com status "done", "skipped" (já existia)
    ou "failed" (com a causa em .error).
    """
    base_name = _apply_template(
        filename_template, artist, title, album, track_number, release_date
    )
    output_path = os.path.join(output_dir, base_name)
    mp3_path = f"{output_path}.mp3"

    if os.path.exists(mp3_path):
        return DownloadResult("skipped")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch1",
        "cachedir": False,  # não escreve cache em ~/.cache (container roda como user não-root)
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"{artist} - {title} audio"])
    except Exception as e:
        return DownloadResult("failed", _humanize_error(e))

    # yt-dlp pode terminar sem exceção mas sem achar resultado (ytsearch vazio)
    if not os.path.exists(mp3_path):
        return DownloadResult("failed", "Nenhum resultado encontrado no YouTube")

    _write_tags(mp3_path, artist, title, album, track_number, cover_url)
    return DownloadResult("done")


def _humanize_error(exc: Exception) -> str:
    """Converte a exceção do yt-dlp numa mensagem curta e legível."""
    msg = re.sub(r"\x1b\[[0-9;]*m", "", str(exc)).strip()  # remove códigos ANSI
    msg = re.sub(r"^ERROR:\s*", "", msg)
    low = msg.lower()

    if "video unavailable" in low:
        return "Vídeo indisponível no YouTube"
    if "private video" in low:
        return "Vídeo privado"
    if "confirm your age" in low or "age-restricted" in low:
        return "Vídeo com restrição de idade"
    if "no video results" in low or "no results" in low:
        return "Nenhum resultado encontrado no YouTube"
    if "ffmpeg" in low or "postprocess" in low:
        return "Erro na conversão de áudio (ffmpeg)"
    if "timed out" in low or "timeout" in low or "connection" in low:
        return "Falha de conexão"
    if not msg:
        return "Erro desconhecido"
    return msg[:200]


def _apply_template(
    template: str,
    artist: str,
    title: str,
    album: str | None,
    track_number: int | None,
    release_date: str | None,
) -> str:
    number_str = f"{track_number:02d}" if track_number else ""
    result = (
        template
        .replace("{artist}", artist or "")
        .replace("{name}", title or "")
        .replace("{album}", album or "")
        .replace("{number}", number_str)
        .replace("{releaseDate}", release_date or "")
    )
    return _safe_name(result).strip(" -_") or _safe_name(f"{artist} - {title}")


def _write_tags(
    filepath: str,
    artist: str,
    title: str,
    album: str | None,
    track_number: int | None,
    cover_url: str | None,
):
    try:
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()

        audio.tags["TIT2"] = TIT2(encoding=3, text=title)
        audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
        if album:
            audio.tags["TALB"] = TALB(encoding=3, text=album)
        if track_number:
            audio.tags["TRCK"] = TRCK(encoding=3, text=str(track_number))
        if cover_url:
            try:
                with urllib.request.urlopen(cover_url, timeout=8) as resp:
                    cover_data = resp.read()
                audio.tags["APIC:Cover"] = APIC(
                    encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data,
                )
            except Exception:
                pass

        audio.save()
    except Exception:
        pass


def _safe_name(name: str) -> str:
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "")
    return name.strip()
