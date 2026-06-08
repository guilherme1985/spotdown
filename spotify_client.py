import os

from dotenv import load_dotenv
from spotdl import Spotdl

load_dotenv()

_client: Spotdl | None = None


def _get_client() -> Spotdl:
    global _client
    if _client is None:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no arquivo .env"
            )
        _client = Spotdl(
            client_id=client_id,
            client_secret=client_secret,
            no_cache=True,
        )
    return _client


def get_playlist_tracks(url: str) -> tuple[str, list[dict]]:
    """Retorna (nome_da_playlist, lista_de_faixas)."""
    client = _get_client()

    try:
        songs = client.search([url])
    except Exception as e:
        raise ValueError(f"Erro ao buscar playlist no Spotify: {e}") from e

    if not songs:
        raise ValueError(
            "Nenhuma faixa encontrada. Verifique se o link está correto e a playlist é pública. "
            "Playlists personalizadas pelo Spotify (Daily Mix, Discover Weekly) não são suportadas."
        )

    playlist_name = _safe_folder_name(songs[0].list_name or _extract_id(url))

    tracks = [
        {
            "artist": song.artist,
            "title": song.name,
            "album": song.album_name,
            "track_number": song.track_number,
            "cover_url": song.cover_url,
        }
        for song in songs
    ]

    return playlist_name, tracks


def _extract_id(url: str) -> str:
    if "spotify.com/playlist/" in url:
        part = url.split("spotify.com/playlist/")[1]
        return part.split("?")[0]
    return url


def _safe_folder_name(name: str) -> str:
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "")
    return name.strip() or "playlist"
