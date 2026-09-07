from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from .database import get_db, init_db
except ImportError:
    from database import get_db, init_db

DATA_DIR = Path(__file__).resolve().parent / "data"
CONTENT_FILE = DATA_DIR / "site_content.json"


DEFAULT_SITE_CONTENT: dict[str, Any] = {
    "home": {
        "hero": {
            "title": "Grupo de Pesquisa em Tecnologias Computacionais",
            "subtitle": "Desenvolvendo o futuro com codigo e inovacao no Instituto Federal de Brasilia.",
        },
        "about": {
            "title": "Quem somos",
            "lead": "O GPTCode e um grupo de pesquisa do Instituto Federal de Educacao, Ciencia e Tecnologia de Brasilia (IFB) dedicado ao desenvolvimento de tecnologias computacionais.",
            "description": "Nossa missao e criar solucoes que abordem problemas complexos e contribuam para o avanco cientifico e tecnologico da sociedade.",
            "primary_button_text": "Conheca nossa equipe",
            "primary_button_link": "/equipe",
            "secondary_button_text": "Nossas publicacoes",
            "secondary_button_link": "/publicacoes",
            "slider": [
                {
                    "id": "about-slide-1",
                    "image": "imagens/logos/gptcode-icon.png",
                    "alt": "Laboratorio GPTCode",
                }
            ],
        },
        "highlight": {
            "type": "none",
            "item_id": "",
        },
        "partners_title": "Parceiros e Apoiadores",
        "partners": [
            {
                "id": "partner-ifb",
                "name": "Instituto Federal de Brasilia",
                "link": "https://www.ifb.edu.br",
                "image": "imagens/logos/Instituto_Federal_de_Brasília.png",
            },
            {
                "id": "partner-cnpq",
                "name": "CNPq",
                "link": "http://dgp.cnpq.br/dgp/espelhogrupo/812978",
                "image": "imagens/logos/cnpq-icon.png",
            },
        ],
    },
    "projects": {
        "page": {
            "title": "Projetos",
            "subtitle": "Conheca os projetos em andamento do GPTCode",
            "section_title": "Projetos em Andamento",
        },
        "items": [],
    },
    "publications": {
        "page": {
            "title": "Publicacoes",
            "subtitle": "Producao cientifica e tecnica do grupo de pesquisa",
            "section_title": "Publicacoes Cientificas",
        },
        "items": [],
    },
    "team": {
        "page": {
            "title": "Nossa Equipe",
            "subtitle": "Conheca os pesquisadores, alunos e colaboradores do GPTCode",
        },
        "categories": [
            {"id": "professores", "title": "Professores Pesquisadores", "empty_message": "Nenhum membro por enquanto"},
            {"id": "graduacao", "title": "Alunos de Graduacao", "empty_message": "Nenhum membro por enquanto"},
            {"id": "tecnico", "title": "Alunos Tecnicos", "empty_message": "Nenhum membro por enquanto"},
            {"id": "externos", "title": "Ex-Alunos do IFB e/ou Colaboradores Externos", "empty_message": "Nenhum membro por enquanto"},
        ],
        "members": [],
    },
    "contact": {
        "items": [],
    },
}


def get_default_site_content() -> dict[str, Any]:
    return deepcopy(DEFAULT_SITE_CONTENT)


def ensure_site_content() -> None:
    init_db()


def load_site_content() -> dict[str, Any]:
    init_db()
    conn = get_db()
    try:
        return _assemble_content(conn)
    finally:
        conn.close()


def save_site_content(content: dict[str, Any]) -> None:
    init_db()
    conn = get_db()
    try:
        _persist_content(conn, content)
    finally:
        conn.close()


def _cfg(conn, chave: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT valor FROM configuracao WHERE chave = ?", (chave,)
    ).fetchone()
    return row["valor"] if row else default


def _assemble_content(conn) -> dict[str, Any]:
    slider = [
        {"id": r["id"], "image": r["imagem"], "alt": r["alt"]}
        for r in conn.execute("SELECT * FROM slider ORDER BY ordem").fetchall()
    ]
    partners = [
        {"id": r["id"], "name": r["nome"], "link": r["link"], "image": r["imagem"]}
        for r in conn.execute("SELECT * FROM parceiro ORDER BY ordem").fetchall()
    ]
    categories = [
        {"id": r["id"], "title": r["titulo"], "empty_message": r["mensagem_vazia"]}
        for r in conn.execute("SELECT * FROM categoria_membro").fetchall()
    ]
    members = [
        {
            "id": r["id"],
            "category": r["id_categoria"],
            "name": r["nome"],
            "role": r["funcao"],
            "github_url": r["github_url"],
            "lattes_url": r["lattes_url"],
            "description": r["descricao"],
            "tags": json.loads(r["tags"]),
            "image": r["imagem"],
        }
        for r in conn.execute("SELECT * FROM membro ORDER BY ordem").fetchall()
    ]
    projects = [
        {
            "id": r["id"],
            "badge": r["badge"],
            "title": r["titulo"],
            "students": r["estudantes"],
            "advisor": r["orientador"],
            "image": r["imagem"],
            "about_url": r["about_url"],
            "about_text": r["about_text"],
        }
        for r in conn.execute("SELECT * FROM projeto ORDER BY ordem").fetchall()
    ]
    publications = [
        {
            "id": r["id"],
            "year": r["ano"],
            "title": r["titulo"],
            "participants": r["participantes"],
            "journal": r["periodico"],
            "doi_url": r["doi_url"],
        }
        for r in conn.execute("SELECT * FROM publicacao ORDER BY ordem").fetchall()
    ]
    contact_items = [
        {
            "id": r["id"],
            "icon": r["icone"],
            "title": r["titulo"],
            "value": r["valor"],
            "subtitle": r["subtitulo"],
            "link": r["link"],
        }
        for r in conn.execute("SELECT * FROM contato ORDER BY ordem").fetchall()
    ]

    return {
        "home": {
            "hero": {
                "title": _cfg(conn, "hero_title"),
                "subtitle": _cfg(conn, "hero_subtitle"),
            },
            "about": {
                "title": _cfg(conn, "about_title"),
                "lead": _cfg(conn, "about_lead"),
                "description": _cfg(conn, "about_description"),
                "primary_button_text": _cfg(conn, "about_primary_button_text"),
                "primary_button_link": _cfg(conn, "about_primary_button_link"),
                "secondary_button_text": _cfg(conn, "about_secondary_button_text"),
                "secondary_button_link": _cfg(conn, "about_secondary_button_link"),
                "slider": slider,
            },
            "highlight": {
                "type": _cfg(conn, "highlight_type", "none"),
                "item_id": _cfg(conn, "highlight_item_id"),
            },
            "partners_title": _cfg(conn, "partners_title"),
            "partners": partners,
        },
        "projects": {
            "page": {
                "title": _cfg(conn, "projects_page_title"),
                "subtitle": _cfg(conn, "projects_page_subtitle"),
                "section_title": _cfg(conn, "projects_section_title"),
            },
            "items": projects,
        },
        "publications": {
            "page": {
                "title": _cfg(conn, "publications_page_title"),
                "subtitle": _cfg(conn, "publications_page_subtitle"),
                "section_title": _cfg(conn, "publications_section_title"),
            },
            "items": publications,
        },
        "team": {
            "page": {
                "title": _cfg(conn, "team_page_title"),
                "subtitle": _cfg(conn, "team_page_subtitle"),
            },
            "categories": categories,
            "members": members,
        },
        "contact": {
            "items": contact_items,
        },
    }


def _upsert_cfg(conn, chave: str, valor: str) -> None:
    conn.execute(
        "INSERT INTO configuracao (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )


def _persist_content(conn, content: dict[str, Any]) -> None:
    home = content.get("home", {})
    hero = home.get("hero", {})
    about = home.get("about", {})
    highlight = home.get("highlight", {})
    projects = content.get("projects", {})
    publications = content.get("publications", {})
    team = content.get("team", {})
    contact = content.get("contact", {})

    with conn:
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
        for chave, valor in configs.items():
            _upsert_cfg(conn, chave, str(valor))

        conn.execute("DELETE FROM slider")
        for i, item in enumerate(about.get("slider", [])):
            conn.execute(
                "INSERT INTO slider (id, imagem, alt, ordem) VALUES (?, ?, ?, ?)",
                (item["id"], item.get("image", ""), item.get("alt", ""), i),
            )

        conn.execute("DELETE FROM parceiro")
        for i, p in enumerate(home.get("partners", [])):
            conn.execute(
                "INSERT INTO parceiro (id, nome, link, imagem, ordem) VALUES (?, ?, ?, ?, ?)",
                (p["id"], p.get("name", ""), p.get("link", ""), p.get("image", ""), i),
            )

        for cat in team.get("categories", []):
            conn.execute(
                "INSERT INTO categoria_membro (id, titulo, mensagem_vazia) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET titulo = excluded.titulo, mensagem_vazia = excluded.mensagem_vazia",
                (cat["id"], cat.get("title", ""), cat.get("empty_message", "")),
            )

        conn.execute("DELETE FROM membro")
        for i, m in enumerate(team.get("members", [])):
            conn.execute(
                "INSERT INTO membro "
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

        conn.execute("DELETE FROM projeto")
        for i, p in enumerate(projects.get("items", [])):
            conn.execute(
                "INSERT INTO projeto "
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

        conn.execute("DELETE FROM publicacao")
        for i, p in enumerate(publications.get("items", [])):
            conn.execute(
                "INSERT INTO publicacao "
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

        conn.execute("DELETE FROM contato")
        for i, c in enumerate(contact.get("items", [])):
            conn.execute(
                "INSERT INTO contato "
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
