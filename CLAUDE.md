# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é este projeto

Ferramenta local para baixar playlists do Spotify como MP3. Tem duas interfaces:
- **Web** (`api.py` + `frontend/`) — servidor FastAPI com UI para acompanhar downloads em tempo real via SSE.
- **CLI** (`main.py`) — linha de comando com barra de progresso via `rich`.

O áudio vem do YouTube (`yt-dlp`); o Spotify é usado apenas para metadados (artista + título). Limite padrão: 50 faixas por playlist.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # preencher com credenciais do Spotify
```

Credenciais em `.env` — obtidas em https://developer.spotify.com/dashboard (basta criar um app, não precisa de redirect URI):
```
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

`ffmpeg` deve estar instalado para conversão de áudio.

## Rodando

### Com Docker (recomendado)
```bash
cp .env.example .env   # preencha antes
docker compose up --build
# acesse http://localhost:8000
```

Os MP3s ficam em `./downloads/` no host (bind mount).

Para mudar o limite de faixas, edite `MAX_TRACKS_PER_PLAYLIST` em `docker-compose.yml`.

### Localmente (dev)
```bash
uvicorn api:app --reload   # web em http://localhost:8000
python main.py "URL_DA_PLAYLIST"  # CLI
```

## Versão

Controlada no arquivo `VERSION`. A versão exibida no footer da UI deve ser atualizada manualmente em `frontend/index.html` junto com o arquivo `VERSION`.

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `api.py` | FastAPI: CRUD de jobs, cancelamento, retry, SSE, serve `frontend/` |
| `db.py` | Persistência SQLite via `aiosqlite`; DB salvo em `DOWNLOAD_DIR/jobs.db` |
| `spotify_client.py` | Autenticação Client Credentials + paginação; retorna `(nome, faixas)` com album/cover/track_number |
| `downloader.py` | Download via `yt-dlp` + gravação de tags ID3 com `mutagen` |
| `main.py` | CLI com rich: lê playlist → loop de download |
| `frontend/` | SPA vanilla JS/CSS; SSE para progresso em tempo real |

**Fluxo web:**  
`POST /api/jobs` → `_run_job` (busca Spotify) → `_run_download_phase` com `asyncio.Semaphore(3)` (3 downloads em paralelo) → SSE a cada 400ms → frontend atualiza faixas em tempo real.

**Estado do job:**  
`status`: `pending → fetching → downloading → completed | error | cancelled`  
`tracks[i].status`: `pending → downloading → done | skipped | failed | cancelled`

**Endpoints de ação:**  
- `DELETE /api/jobs/{id}` — cancela job em andamento (seta `asyncio.Event`; downloads ativos terminam, pendentes viram `cancelled`)  
- `POST /api/jobs/{id}/retry` — re-tenta faixas com status `failed` ou `cancelled`

**Persistência:**  
Jobs são salvos no SQLite após cada mudança de status de faixa. Ao reiniciar, jobs interrompidos ficam com status `cancelled` e faixas `pending/downloading` são marcadas como `cancelled` (recuperáveis via retry).

## Variáveis de ambiente relevantes

| Variável | Padrão | Descrição |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | — | obrigatório |
| `SPOTIFY_CLIENT_SECRET` | — | obrigatório |
| `MAX_TRACKS_PER_PLAYLIST` | `50` | trunca playlists maiores |
| `DOWNLOAD_DIR` | `downloads` | pasta de saída dos MP3s e do `jobs.db` |
| `SPOTIFY_FETCH_TIMEOUT` | `150` | segundos para buscar a playlist no Spotify (inclui matching no YouTube por faixa) antes de desistir |

## Estrutura de saída

```
downloads/
├── Nome da Playlist/
│   ├── 01 - Artista - Título.mp3   ← com tags ID3 + capa embutida
│   └── ...
└── jobs.db
```

## Limitações conhecidas

- Apenas playlists **públicas** (Client Credentials flow).
- Correspondência Spotify → YouTube é heurística; músicas raras podem baixar a versão errada.
