import os

import spotipy
from dotenv import load_dotenv
from spotdl import Spotdl
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

_client: Spotdl | None = None
_search_client: spotipy.Spotify | None = None


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


def _get_search_client() -> spotipy.Spotify:
    """Cliente spotipy oficial para busca por nome (artista/álbum/playlist)."""
    global _search_client
    if _search_client is None:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "Credenciais não configuradas. Informe o Client ID e Client Secret do Spotify."
            )
        auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
        _search_client = spotipy.Spotify(auth_manager=auth)
    return _search_client


def _find_spotify_url(query: str, query_type: str) -> str:
    """Busca artista/álbum/playlist por nome e retorna a URL Spotify do primeiro resultado."""
    sp = _get_search_client()
    spotify_type = {"artist": "artist", "album": "album", "mood": "playlist"}[query_type]
    result = sp.search(query, type=spotify_type, limit=5)
    items = (result.get(f"{spotify_type}s") or {}).get("items") or []
    items = [i for i in items if i]
    if not items:
        raise ValueError(f"Nenhum resultado encontrado para '{query}'. Tente um termo diferente.")
    return items[0]["external_urls"]["spotify"]


def connect_with_credentials(client_id: str, client_secret: str) -> None:
    """Cria novo cliente com as credenciais fornecidas, validando antes de aceitar."""
    global _client, _search_client
    new_client = Spotdl(client_id=client_id, client_secret=client_secret, no_cache=True)
    new_client.search(["spotify:track:4uLU6hMCjMI75M1A2tKUQC"])
    _client = new_client
    _search_client = None  # força re-criação com as novas credenciais


def get_playlist_tracks(url: str, query_type: str = "url") -> tuple[str, list[dict]]:
    """Retorna (nome_da_playlist, lista_de_faixas)."""
    # Para buscas por nome, resolve primeiro para URL Spotify via spotipy oficial
    if query_type != "url":
        url = _find_spotify_url(url, query_type)

    client = _get_client()

    try:
        songs = client.search([url])
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
