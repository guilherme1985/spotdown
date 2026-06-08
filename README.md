# SpotDownload

Baixe playlists públicas do Spotify como MP3 com uma interface web local. As músicas são buscadas no YouTube via `yt-dlp` e salvas com tags ID3 completas (artista, título, álbum e capa).

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- Credenciais de um app no [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

## Como obter as credenciais do Spotify

1. Acesse [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) e faça login com sua conta Spotify.
2. Clique em **Create app**.
3. Preencha nome e descrição (qualquer valor serve). Em **Redirect URI**, adicione exatamente: `http://127.0.0.1:5001/callback`
4. Após criar, acesse **Settings** e copie o **Client ID** e o **Client Secret**.

> O Redirect URI precisa ser registrado no Dashboard para o login funcionar. Se usar uma porta diferente, ajuste `SPOTIFY_REDIRECT_URI` no `.env` e no Dashboard.

## Instalação

```bash
git clone <url-do-repositorio>
cd spotdownload

# Crie o arquivo de credenciais a partir do exemplo
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
SPOTIFY_CLIENT_ID=cole_seu_client_id_aqui
SPOTIFY_CLIENT_SECRET=cole_seu_client_secret_aqui
```

## Uso

### Interface web (recomendado)

```bash
docker compose up --build
```

Acesse **http://localhost:5001** no navegador.

Cole o link de qualquer playlist pública do Spotify e clique em **Baixar**. O progresso de cada faixa é exibido em tempo real.

As músicas são salvas em `./downloads/<nome da playlist>/` no formato `Artista - Título.mp3`.

### CLI (opcional, sem Docker)

```bash
pip install -r requirements.txt
# instale também o ffmpeg: sudo apt install ffmpeg  /  brew install ffmpeg

python main.py "https://open.spotify.com/playlist/..."

# pasta de destino personalizada
python main.py "https://open.spotify.com/playlist/..." -o ~/Músicas
```

## Configuração

| Variável | Padrão | Descrição |
|---|---|---|
| `SPOTIFY_CLIENT_ID` | — | obrigatório |
| `SPOTIFY_CLIENT_SECRET` | — | obrigatório |
| `MAX_TRACKS_PER_PLAYLIST` | `50` | limite de faixas por playlist |

Para alterar o limite, edite `MAX_TRACKS_PER_PLAYLIST` em `docker-compose.yml`.

## Observações

- Funciona apenas com playlists **públicas**.
- O áudio vem do YouTube — a correspondência é heurística e pode baixar uma versão diferente em músicas menos conhecidas.
- O histórico de downloads persiste em `./downloads/jobs.db` e sobrevive a reinicializações do container.
