#!/bin/sh
set -e

# Ajusta o dono da pasta de downloads (bind mount) para o usuário alvo e
# corrige arquivos antigos criados como root. Depois dropa o privilégio.
PUID=${PUID:-1000}
PGID=${PGID:-1000}

mkdir -p /app/downloads
chown -R "$PUID:$PGID" /app/downloads 2>/dev/null || true

mkdir -p /app/data
chown -R "$PUID:$PGID" /app/data 2>/dev/null || true

# gosu reseta HOME para "/" (o UID alvo não existe em /etc/passwd), o que faz o
# spotdl tentar criar /.config no import e falhar. Forçamos um HOME gravável.
exec gosu "$PUID:$PGID" env HOME=/tmp "$@"
