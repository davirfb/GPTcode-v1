from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_FILE = DATA_DIR / "gptcode.db"
CONTENT_FILE = DATA_DIR / "site_content.json"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    ativo INTEGER NOT NULL DEFAULT 1,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS configuracao (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS slider (
    id TEXT PRIMARY KEY,
    imagem TEXT NOT NULL,
    alt TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parceiro (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    link TEXT NOT NULL DEFAULT '',
    imagem TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS categoria_membro (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    mensagem_vazia TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS membro (
    id TEXT PRIMARY KEY,
    id_categoria TEXT NOT NULL REFERENCES categoria_membro(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    funcao TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '',
    lattes_url TEXT NOT NULL DEFAULT '',
    descricao TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    imagem TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS projeto (
    id TEXT PRIMARY KEY,
    badge TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    estudantes TEXT NOT NULL DEFAULT '',
    orientador TEXT NOT NULL DEFAULT '',
    imagem TEXT NOT NULL DEFAULT '',
    about_url TEXT NOT NULL DEFAULT '',
    about_text TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS publicacao (
    id TEXT PRIMARY KEY,
    ano INTEGER NOT NULL DEFAULT 0,
    titulo TEXT NOT NULL,
    participantes TEXT NOT NULL DEFAULT '',
    periodico TEXT NOT NULL DEFAULT '',
    doi_url TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contato (
    id TEXT PRIMARY KEY,
    icone TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL,
    valor TEXT NOT NULL DEFAULT '',
    subtitulo TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mensagem_contato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    enviado_em TEXT NOT NULL DEFAULT (datetime('now')),
    lido INTEGER NOT NULL DEFAULT 0
);
"""


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    conn = get_db()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        _migrate_from_json(conn)
    finally:
        conn.close()


def _migrate_from_json(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) FROM projeto").fetchone()
    if row[0] > 0:
        return

    if not CONTENT_FILE.exists():
        return

    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    home = data.get("home", {})
    hero = home.get("hero", {})
    about = home.get("about", {})
    highlight = home.get("highlight", {})
    projects = data.get("projects", {})
    publications = data.get("publications", {})
    team = data.get("team", {})
    contact = data.get("contact", {})

    configs = {
        "hero_title": hero.get("title", ""),
        "hero_subtitle": hero.get("subtitle", ""),
        "about_title": about.get("title", ""),
        "about_lead": about.get("lead", ""),
        "about_description": about.get("description", ""),
        "about_primary_button_text": about.get("primary_button_text", ""),
        "about_primary_button_link": about.get("primary_button_link", ""),
        "about_secondary_button_text": about.get("secondary_button_text", ""),
        "about_secondary_button_link": about.get("secondary_button_link", ""),
        "partners_title": home.get("partners_title", ""),
        "highlight_type": highlight.get("type", "none"),
        "highlight_item_id": highlight.get("item_id", "") or "",
        "projects_page_title": projects.get("page", {}).get("title", ""),
        "projects_page_subtitle": projects.get("page", {}).get("subtitle", ""),
        "projects_section_title": projects.get("page", {}).get("section_title", ""),
        "publications_page_title": publications.get("page", {}).get("title", ""),
        "publications_page_subtitle": publications.get("page", {}).get("subtitle", ""),
        "publications_section_title": publications.get("page", {}).get("section_title", ""),
        "team_page_title": team.get("page", {}).get("title", ""),
        "team_page_subtitle": team.get("page", {}).get("subtitle", ""),
    }

    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO configuracao (chave, valor) VALUES (?, ?)",
            list(configs.items()),
        )

        for i, item in enumerate(about.get("slider", [])):
            conn.execute(
                "INSERT OR IGNORE INTO slider (id, imagem, alt, ordem) VALUES (?, ?, ?, ?)",
                (item["id"], item.get("image", ""), item.get("alt", ""), i),
            )

        for i, p in enumerate(home.get("partners", [])):
            conn.execute(
                "INSERT OR IGNORE INTO parceiro (id, nome, link, imagem, ordem) VALUES (?, ?, ?, ?, ?)",
                (p["id"], p.get("name", ""), p.get("link", ""), p.get("image", ""), i),
            )

        for cat in team.get("categories", []):
            conn.execute(
                "INSERT OR IGNORE INTO categoria_membro (id, titulo, mensagem_vazia) VALUES (?, ?, ?)",
                (cat["id"], cat.get("title", ""), cat.get("empty_message", "")),
            )

        for i, m in enumerate(team.get("members", [])):
            conn.execute(
                "INSERT OR IGNORE INTO membro "
                "(id, id_categoria, nome, funcao, github_url, lattes_url, descricao, tags, imagem, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    m["id"],
                    m.get("category", ""),
                    m.get("name", ""),
                    m.get("role", ""),
                    m.get("github_url", ""),
                    m.get("lattes_url", ""),
                    m.get("description", ""),
                    json.dumps(m.get("tags", [])),
                    m.get("image", ""),
                    i,
                ),
            )

        for i, p in enumerate(projects.get("items", [])):
            conn.execute(
                "INSERT OR IGNORE INTO projeto "
                "(id, badge, titulo, estudantes, orientador, imagem, about_url, about_text, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    p["id"],
                    p.get("badge", ""),
                    p.get("title", ""),
                    p.get("students", ""),
                    p.get("advisor", ""),
                    p.get("image", ""),
                    p.get("about_url", ""),
                    p.get("about_text", ""),
                    i,
                ),
            )

        for i, p in enumerate(publications.get("items", [])):
            conn.execute(
                "INSERT OR IGNORE INTO publicacao "
                "(id, ano, titulo, participantes, periodico, doi_url, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    p["id"],
                    p.get("year", 0),
                    p.get("title", ""),
                    p.get("participants", ""),
                    p.get("journal", ""),
                    p.get("doi_url", ""),
                    i,
                ),
            )

        for i, c in enumerate(contact.get("items", [])):
            conn.execute(
                "INSERT OR IGNORE INTO contato "
                "(id, icone, titulo, valor, subtitulo, link, ordem) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    c["id"],
                    c.get("icon", ""),
                    c.get("title", ""),
                    c.get("value", ""),
                    c.get("subtitle", ""),
                    c.get("link", ""),
                    i,
                ),
            )


def add_mensagem(nome: str, email: str, mensagem: str) -> None:
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "INSERT INTO mensagem_contato (nome, email, mensagem) VALUES (?, ?, ?)",
                (nome, email, mensagem),
            )
    finally:
        conn.close()


def get_mensagens(apenas_nao_lidas: bool = False) -> list[dict]:
    conn = get_db()
    try:
        query = "SELECT * FROM mensagem_contato"
        if apenas_nao_lidas:
            query += " WHERE lido = 0"
        query += " ORDER BY enviado_em DESC"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def mark_mensagem_lida(mensagem_id: int) -> None:
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "UPDATE mensagem_contato SET lido = 1 WHERE id = ?", (mensagem_id,)
            )
    finally:
        conn.close()


def count_nao_lidas() -> int:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM mensagem_contato WHERE lido = 0"
        ).fetchone()
        return row[0]
    finally:
        conn.close()
