"""Recursos por requisicao: conexao com o banco e usuario autenticado."""

from __future__ import annotations

import sqlite3

from flask import g

from backend.database import connect


def get_db() -> sqlite3.Connection:
    """Uma conexao por requisicao, fechada em `fechar_db` (teardown)."""
    if "db" not in g:
        g.db = connect()
    return g.db


def fechar_db(_erro=None) -> None:
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


def usuario_id() -> int | None:
    usuario = getattr(g, "admin_user", None) or {}
    return usuario.get("usuario_id")


def esta_autenticado() -> bool:
    return bool(getattr(g, "admin_user", None))
