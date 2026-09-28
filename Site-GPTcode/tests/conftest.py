"""Configuracao dos testes: cada teste usa um banco SQLite novo e vazio."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Precisa existir antes de importar o app (que inicializa o banco no import).
_PASTA_TEMP = Path(tempfile.mkdtemp(prefix="gptcode-testes-"))
os.environ["GPTCODE_DB_PATH"] = str(_PASTA_TEMP / "importacao.db")
os.environ["API_TOKEN"] = "token-de-teste"
os.environ.pop("ADMIN_ALLOWED_EMAILS", None)
os.environ.pop("NOTIFICATION_EMAIL_FROM", None)

from backend import uploads  # noqa: E402
from backend.app import app as flask_app  # noqa: E402
from backend.database import connect, init_db  # noqa: E402

TOKEN = {"Authorization": "Bearer token-de-teste"}


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "teste.db"
    monkeypatch.setenv("GPTCODE_DB_PATH", str(caminho))
    # uploads dos testes vao para a pasta temporaria, nao para frontend/static
    monkeypatch.setattr(uploads, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(uploads, "UPLOADS_DIR", tmp_path / "uploads")
    init_db(caminho, conteudo_inicial={})
    return caminho


@pytest.fixture()
def conn(banco):
    conexao = connect(banco)
    yield conexao
    conexao.close()


@pytest.fixture()
def cliente(banco):
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture()
def admin(cliente):
    """Cliente com sessao de administrador (sem passar pelo Firebase)."""
    with cliente.session_transaction() as sessao:
        sessao["admin"] = {
            "email": "admin@teste.com",
            "name": "Admin",
            "usuario_id": None,
            "expira_em": time.time() + 3600,
        }
    return cliente


@pytest.fixture()
def categoria(cliente):
    resposta = cliente.post("/api/v1/categorias", json={"titulo": "Professores Pesquisadores"}, headers=TOKEN)
    assert resposta.status_code == 201, resposta.json
    return resposta.json


@pytest.fixture()
def professor(cliente, categoria):
    resposta = cliente.post(
        "/api/v1/membros",
        json={"categoria_id": categoria["id"], "nome": "Prof. Dr. Dauster Souza Pereira", "funcao": "Coordenador"},
        headers=TOKEN,
    )
    assert resposta.status_code == 201, resposta.json
    return resposta.json
