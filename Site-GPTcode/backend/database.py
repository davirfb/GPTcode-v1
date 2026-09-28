"""Conexao com o SQLite e criacao/migracao do schema.

O schema oficial fica em `database/schema.sql`. A versao do banco e
controlada por `PRAGMA user_version`; ao encontrar um banco antigo (v1),
`init_db` gera um banco novo em arquivo temporario, copia os dados
validados e so entao substitui o original, guardando um backup `.v1.bak`.
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
LEGACY_JSON_FILE = DATA_DIR / "site_content.json"
SCHEMA_VERSION = 2

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


def init_db(caminho: Path | str | None = None, conteudo_inicial: dict | None = None) -> list[str]:
    """Garante o banco na versao atual. Retorna avisos da migracao (se houver)."""
    from backend import migracao_v1

    caminho = Path(caminho or db_path())
    conn = connect(caminho)
    try:
        if versao(conn) >= SCHEMA_VERSION:
            return []
        conteudo, mensagens = None, []
        lido = migracao_v1.ler_conteudo_v1(conn)
        if lido:
            conteudo, mensagens = lido
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    if conteudo is None:
        conteudo = conteudo_inicial if conteudo_inicial is not None else migracao_v1.ler_conteudo_json(LEGACY_JSON_FILE)

    temporario = caminho.with_name(caminho.name + ".novo")
    temporario.unlink(missing_ok=True)
    novo = connect(temporario)
    try:
        criar_schema(novo)
        avisos = migracao_v1.semear(novo, conteudo, mensagens) if conteudo else []
    except Exception:
        novo.close()
        temporario.unlink(missing_ok=True)
        raise
    novo.close()

    if caminho.exists() and caminho.stat().st_size > 0 and lido:
        shutil.copy2(caminho, caminho.with_name(caminho.name + ".v1.bak"))
    for sufixo in ("-wal", "-shm"):
        caminho.with_name(caminho.name + sufixo).unlink(missing_ok=True)
    os.replace(temporario, caminho)

    for aviso in avisos:
        log.warning("migracao: %s", aviso)
    return avisos
