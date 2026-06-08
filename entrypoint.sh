#!/bin/sh
set -e

# Ajusta o dono da pasta de downloads (bind mount) para o usuário alvo e
# corrige arquivos antigos criados como root. Depois dropa o privilégio.
PUID=${PUID:-1000}
PGID=${PGID:-1000}

mkdir -p /app/downloads
chown -R "$PUID:$PGID" /app/downloads 2>/dev/null || true

exec gosu "$PUID:$PGID" "$@"
