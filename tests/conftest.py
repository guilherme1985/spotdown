"""Configuração compartilhada dos testes.

Aponta DOWNLOAD_DIR e credenciais para valores de teste ANTES de qualquer
import dos módulos do app (db.py e spotify_client.py leem env no import).
"""
import os
import sys
import tempfile

# Garante que a raiz do projeto esteja no sys.path (rodar pytest de qualquer lugar)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Credenciais fake para os imports não falharem; nenhum teste faz chamada real.
os.environ["SPOTIFY_CLIENT_ID"] = "test-client-id"
os.environ["SPOTIFY_CLIENT_SECRET"] = "test-client-secret"
# Saída/banco isolados em diretório temporário.
os.environ["DOWNLOAD_DIR"] = tempfile.mkdtemp(prefix="spotdl-test-")

import pytest


@pytest.fixture(autouse=True)
def _clean_job_state():
    """Limpa o estado em memória de jobs antes de cada teste para isolá-los."""
    import api
    api._jobs.clear()
    api._cancel_events.clear()
    yield
    api._jobs.clear()
    api._cancel_events.clear()
