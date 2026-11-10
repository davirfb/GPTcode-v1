"""Conexão com o SQLite e criação/migração do schema (versão 4).

O schema oficial fica em `database/schema.sql`; a versão é controlada por `PRAGMA user_version`.
Instalação nova: o banco nasce de uma cópia de `backend/data/semente.db` (conteúdo público do site).
Banco da versão 2 (a anterior, também com login pelo Firebase) é migrado sem perder dados.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
SCHEMA_FILE = PROJECT_DIR / "database" / "schema.sql"
# Conteúdo público inicial (versionado no git). O banco em uso, gptcode.db, NÃO vai para o git:
# guarda os e-mails de quem acessa o painel e as mensagens dos visitantes.
SEMENTE_DB = DATA_DIR / "semente.db"
SCHEMA_VERSION = 4

log = logging.getLogger(__name__)


def db_path() -> Path:
    configurado = os.getenv("GPTCODE_DB_PATH", "").strip()
    return Path(configurado) if configurado else DATA_DIR / "gptcode.db"


def connect(caminho: Path | str | None = None) -> sqlite3.Connection:
    caminho = Path(caminho or db_path())
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho), timeout=10)
    conn.row_factory = sqlite3.Row
    # O SQLite nao verifica chaves estrangeiras por padrao.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def versao(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


_COMANDOS_V4 = (
    "ALTER TABLE usuario ADD COLUMN sessoes_validas_desde REAL",
    """CREATE TABLE IF NOT EXISTS limite_acesso (
        chave          TEXT    PRIMARY KEY,
        email          TEXT    COLLATE NOCASE,
        tentativas     INTEGER NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
        janela_inicio  TEXT    NOT NULL,
        bloqueado_ate  TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_limite_email ON limite_acesso (email)",
    "PRAGMA user_version = 4",
)


def migrar_v2_para_v4(conn: sqlite3.Connection) -> None:
    """v4: logout que invalida a sessão no servidor e limite de mensagens por IP no contato."""
    try:
        conn.execute("BEGIN")
        for comando in _COMANDOS_V4:
            conn.execute(comando)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def init_db(caminho: Path | str | None = None, vazio: bool = False) -> None:
    """Garante o banco na versão atual. `vazio=True` cria só o schema, sem o conteúdo da semente."""
    caminho = Path(caminho or db_path())
    if not caminho.exists():
        caminho.parent.mkdir(parents=True, exist_ok=True)  # GPTCODE_DB_PATH pode apontar para pasta nova
        if SEMENTE_DB.exists() and not vazio:
            shutil.copy2(SEMENTE_DB, caminho)
        else:
            novo = connect(caminho)
            try:
                criar_schema(novo)
            finally:
                novo.close()
    conn = connect(caminho)
    try:
        atual = versao(conn)
        if atual == 2:
            migrar_v2_para_v4(conn)
        elif atual != SCHEMA_VERSION:
            raise RuntimeError(f"Banco na versão {atual}: só as versões 2 e {SCHEMA_VERSION} são suportadas.")
    finally:
        conn.close()
