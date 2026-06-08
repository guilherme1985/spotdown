"""Testes das funções puras e da lógica de busca do spotify_client."""
import spotify_client


def test_extract_id_from_url():
    url = "https://open.spotify.com/playlist/37i9dQZF1DX0?si=abc123"
    assert spotify_client._extract_id(url) == "37i9dQZF1DX0"


def test_extract_id_from_url_without_query():
    url = "https://open.spotify.com/playlist/37i9dQZF1DX0"
    assert spotify_client._extract_id(url) == "37i9dQZF1DX0"


def test_extract_id_passthrough():
    # se não for URL de playlist, retorna como veio
    assert spotify_client._extract_id("37i9dQZF1DX0") == "37i9dQZF1DX0"


def test_safe_folder_name_removes_invalid():
    assert spotify_client._safe_folder_name('Rock/Pop:90s') == "RockPop90s"


def test_safe_folder_name_empty_fallback():
    assert spotify_client._safe_folder_name("   ") == "playlist"
    assert spotify_client._safe_folder_name('/:*?') == "playlist"


def test_search_playlists_maps_fields(monkeypatch):
    """search_playlists deve mapear a resposta crua do spotipy para o formato da UI."""
    fake_response = {
        "playlists": {
            "items": [
                {
                    "name": "90s Rock",
                    "external_urls": {"spotify": "https://open.spotify.com/playlist/abc"},
                    "images": [{"url": "http://img/cover.jpg"}],
                    "tracks": {"total": 50},
                    "owner": {"display_name": "DJ Test"},
                },
                None,  # spotipy às vezes retorna itens None — devem ser filtrados
            ]
        }
    }

    class FakeSp:
        def search(self, q, type, limit):
            return fake_response

    monkeypatch.setattr(spotify_client, "_get_search_client", lambda: FakeSp())

    result = spotify_client.search_playlists("rock", 5)
    assert len(result) == 1
    assert result[0]["name"] == "90s Rock"
    assert result[0]["url"] == "https://open.spotify.com/playlist/abc"
    assert result[0]["image"] == "http://img/cover.jpg"
    assert result[0]["tracks_total"] == 50
    assert result[0]["owner"] == "DJ Test"


def test_search_playlists_handles_items_total_key(monkeypatch):
    """Algumas respostas usam 'items.total' em vez de 'tracks.total'."""
    fake_response = {
        "playlists": {
            "items": [
                {
                    "name": "Lista",
                    "external_urls": {"spotify": "u"},
                    "images": [],
                    "items": {"total": 12},
                    "owner": {"display_name": "x"},
                }
            ]
        }
    }

    class FakeSp:
        def search(self, q, type, limit):
            return fake_response

    monkeypatch.setattr(spotify_client, "_get_search_client", lambda: FakeSp())
    result = spotify_client.search_playlists("x", 5)
    assert result[0]["tracks_total"] == 12
    assert result[0]["image"] is None


def test_get_tracks_by_artist_filters_and_dedups(monkeypatch):
    """_get_tracks_by_artist deve filtrar pelo artista e remover duplicatas."""
    def make_track(title, artist="Coldplay"):
        return {
            "name": title,
            "artists": [{"name": artist}],
            "album": {"name": "Alb", "images": [{"url": "c"}], "release_date": "2020"},
            "track_number": 1,
        }

    pages = [
        {"tracks": {"items": [make_track("Yellow"), make_track("Paradise")]}},
        {"tracks": {"items": [make_track("Yellow"),  # duplicata
                              make_track("Hello", artist="Adele")]}},  # outro artista
        {"tracks": {"items": []}},  # fim
    ]

    class FakeSp:
        def __init__(self):
            self.calls = 0

        def search(self, q, type, limit, offset):
            page = self.calls if self.calls < len(pages) else len(pages) - 1
            self.calls += 1
            return pages[page] if self.calls <= len(pages) else {"tracks": {"items": []}}

    monkeypatch.setattr(spotify_client, "_get_search_client", lambda: FakeSp())

    name, tracks = spotify_client._get_tracks_by_artist("Coldplay")
    titles = [t["title"] for t in tracks]
    assert name == "Coldplay"
    assert titles == ["Yellow", "Paradise"]  # sem duplicata, sem Adele
