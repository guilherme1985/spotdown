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
                "Credenciais não configuradas. Informe o Client ID e Client Secret do Spotify."
            )
        _client = Spotdl(client_id=client_id, client_secret=client_secret, no_cache=True)
    return _client


def connect_with_credentials(client_id: str, client_secret: str) -> None:
    """Cria um novo cliente com as credenciais fornecidas, substituindo o atual."""
    global _client
    new_client = Spotdl(client_id=client_id, client_secret=client_secret, no_cache=True)
    # Faz uma busca simples para validar as credenciais antes de aceitar
    new_client.search(["spotify:track:4uLU6hMCjMI75M1A2tKUQC"])
    _client = new_client


_QUERY_PREFIXES = {
    "url":    None,
    "artist": "artist:",
    "album":  "album:",
    "mood":   "playlist:",
}


def get_playlist_tracks(url: str, query_type: str = "url") -> tuple[str, list[dict]]:
    """Retorna (nome_da_playlist, lista_de_faixas)."""
    client = _get_client()

    prefix = _QUERY_PREFIXES.get(query_type)
    query  = f"{prefix}{url}" if prefix else url

    try:
        songs = client.search([query])
    except Exception as e:
        raise ValueError(f"Erro ao buscar no Spotify: {e}") from e

    if not songs:
        raise ValueError("Nenhuma faixa encontrada. Verifique o termo buscado.")

    if query_type == "artist":
        folder = songs[0].artist or url
    elif query_type == "album":
        folder = songs[0].album_name or url
    else:
        folder = songs[0].list_name or _extract_id(url)

    playlist_name = _safe_folder_name(folder)

    tracks = [
        {
            "artist": song.artist,
            "title": song.name,
            "album": song.album_name,
            "track_number": song.track_number,
            "cover_url": song.cover_url,
            "release_date": song.date or "",
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
