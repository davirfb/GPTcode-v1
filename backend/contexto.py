"""Recursos por requisicao: conexao com o banco e usuario autenticado."""

from __future__ import annotations

import os
import sqlite3

from flask import g, url_for

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
    usuario = getattr(g, "usuario", None) or {}
    return usuario.get("id")


def esta_autenticado() -> bool:
    return bool(getattr(g, "usuario", None))


def url_externa(endpoint: str, **valores) -> str:
    """Endereço completo para e-mails e links de submissão.

    Com SITE_URL definido (ex.: https://gptcode-ifb.onrender.com), o domínio vem
    da configuração e não do cabeçalho Host da requisição, que quem envia pode forjar
    (o link do e-mail apontaria para um site falso)."""
    base = os.getenv("SITE_URL", "").strip().rstrip("/")
    if base:
        return base + url_for(endpoint, **valores)
    return url_for(endpoint, _external=True, **valores)


def url_do_link(link: dict) -> str:
    """Endereço público do formulário de um link de uso único."""
    return url_externa("submit_resource", recurso=link["recurso"], token=link["token"])
