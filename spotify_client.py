import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()


def create_client() -> spotipy.Spotify:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "Defina SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no arquivo .env"
        )

    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return spotipy.Spotify(auth_manager=auth)


def get_playlist_tracks(url: str) -> tuple[str, list[dict]]:
    """Retorna (nome_da_playlist, lista_de_faixas) a partir de uma URL de playlist."""
    sp = create_client()

    playlist_id = _extract_id(url)

    info = sp.playlist(playlist_id, fields="name")
    name = _safe_folder_name(info.get("name") or playlist_id)

    results = sp.playlist_tracks(
        playlist_id,
        fields="items(track(name,artists(name),album(name,images),track_number)),next",
    )

    tracks = []
    while results:
        for item in results["items"]:
            track = item.get("track")
            if not track:
                continue
            artist = track["artists"][0]["name"] if track["artists"] else "Desconhecido"
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


def _safe_folder_name(name: str) -> str:
    invalid = r'\/:*?"<>|'
    for ch in invalid:
        name = name.replace(ch, "")
    return name.strip() or "playlist"


def _extract_id(url: str) -> str:
    """Extrai o ID da playlist da URL ou retorna como está."""
    # https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
    if "spotify.com/playlist/" in url:
        part = url.split("spotify.com/playlist/")[1]
        return part.split("?")[0]
    return url
