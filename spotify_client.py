import os
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:5001/callback")
SCOPES = "playlist-read-private playlist-read-collaborative"
_download_dir = os.getenv("DOWNLOAD_DIR", "downloads")
CACHE_PATH = os.path.join(_download_dir, ".spotify_token_cache")


def _auth_manager() -> SpotifyOAuth:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no arquivo .env"
        )
    Path(_download_dir).mkdir(parents=True, exist_ok=True)
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=False,
    )


def create_client() -> spotipy.Spotify:
    mgr = _auth_manager()
    if not mgr.get_cached_token():
        raise PermissionError("Não autenticado. Conecte sua conta Spotify primeiro.")
    return spotipy.Spotify(auth_manager=mgr)


def get_auth_url() -> str:
    return _auth_manager().get_authorize_url()


def handle_callback(code: str):
    _auth_manager().get_access_token(code)


def is_authenticated() -> bool:
    try:
        return bool(_auth_manager().get_cached_token())
    except Exception:
        return False


def get_playlist_tracks(url: str) -> tuple[str, list[dict]]:
    """Retorna (nome_da_playlist, lista_de_faixas)."""
    sp = create_client()
    playlist_id = _extract_id(url)

    try:
        info = sp.playlist(playlist_id, fields="name")
    except SpotifyException as e:
        if e.http_status == 404:
            raise ValueError(
                "Playlist não encontrada. Confirme que o link está correto e a playlist é pública. "
                "Playlists personalizadas pelo Spotify (Daily Mix, Discover Weekly) não são suportadas."
            ) from e
        raise

    name = _safe_folder_name(info.get("name") or playlist_id)

    try:
        results = sp.playlist_tracks(playlist_id)
    except SpotifyException as e:
        if e.http_status == 403:
            raise ValueError(
                "Acesso negado. Confirme que a playlist é pública ou compartilhada com você."
            ) from e
        if e.http_status == 404:
            raise ValueError("Não foi possível ler as faixas desta playlist.") from e
        raise

    tracks = []
    while results:
        for item in results["items"]:
            track = item.get("track")
            if not track:
                continue
            artist = track["artists"][0]["name"] if track.get("artists") else "Desconhecido"
            album = track.get("album") or {}
            images = album.get("images") or []
            tracks.append({
                "artist": artist,
                "title": track["name"],
                "album": album.get("name"),
                "track_number": track.get("track_number"),
                "cover_url": images[0]["url"] if images else None,
            })
        results = sp.next(results) if results.get("next") else None

    return name, tracks


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
