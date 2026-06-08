import os
import urllib.request

import yt_dlp
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, TRCK
from mutagen.mp3 import MP3

DEFAULT_TEMPLATE = "{artist} - {name}"


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
) -> bool | None:
    """Busca no YouTube e baixa o áudio como MP3.
    Retorna True (baixado), None (já existia) ou False (erro).
    """
    base_name = _apply_template(
        filename_template, artist, title, album, track_number, release_date
    )
    output_path = os.path.join(output_dir, base_name)

    if os.path.exists(f"{output_path}.mp3"):
        return None

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
        _write_tags(f"{output_path}.mp3", artist, title, album, track_number, cover_url)
        return True
    except Exception:
        return False


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
