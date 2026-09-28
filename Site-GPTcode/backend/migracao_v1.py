"""Migracao do modelo v1 (conteudo desnormalizado) para o modelo v2.

O v1 guardava o conteudo como no antigo site_content.json: ids em texto,
"badge" misturando modalidade e periodo, estudantes/autores/tags como
texto unico e string vazia no lugar de NULL. Aqui esse conteudo e lido e
regravado pelo repositorio, passando pelas mesmas validacoes da aplicacao.
Valores que violam as regras sao descartados e listados como avisos.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from backend import repositorio as repo
from backend import validadores as v
from backend.erros import ErroDominio, ValidacaoErro

# Valores de exemplo que ficaram no cadastro antigo e nao sao dados reais.
_PLACEHOLDERS = {"https://github.com/usuario", "admin123"}


def _tem_tabelas_v1(conn: sqlite3.Connection) -> bool:
    colunas = {linha[1] for linha in conn.execute("PRAGMA table_info(projeto)")}
    return "badge" in colunas


def ler_conteudo_v1(conn: sqlite3.Connection) -> tuple[dict, list[dict]] | None:
    """Monta o dict de conteudo a partir das tabelas v1 (ou None se nao houver)."""
    if not _tem_tabelas_v1(conn):
        return None
    conn.row_factory = sqlite3.Row

    def cfg(chave: str, padrao: str = "") -> str:
        linha = conn.execute("SELECT valor FROM configuracao WHERE chave = ?", (chave,)).fetchone()
        return linha["valor"] if linha else padrao

    conteudo = {
        "config": {chave: cfg(chave) for chave in v.CHAVES_CONFIGURACAO},
        "highlight": {"type": cfg("highlight_type", "none"), "item_id": cfg("highlight_item_id")},
        "slider": [
            {"id": r["id"], "image": r["imagem"], "alt": r["alt"]}
            for r in conn.execute("SELECT * FROM slider ORDER BY ordem")
        ],
        "partners": [
            {"id": r["id"], "name": r["nome"], "link": r["link"], "image": r["imagem"]}
            for r in conn.execute("SELECT * FROM parceiro ORDER BY ordem")
        ],
        "categories": [
            {"id": r["id"], "title": r["titulo"], "empty_message": r["mensagem_vazia"]}
            for r in conn.execute("SELECT * FROM categoria_membro")
        ],
        "members": [
            {
                "id": r["id"],
                "category": r["id_categoria"],
                "name": r["nome"],
                "role": r["funcao"],
                "github_url": r["github_url"],
                "lattes_url": r["lattes_url"],
                "description": r["descricao"],
                "tags": json.loads(r["tags"] or "[]"),
                "image": r["imagem"],
            }
            for r in conn.execute("SELECT * FROM membro ORDER BY ordem")
        ],
        "projects": [
            {
                "id": r["id"],
                "badge": r["badge"],
                "title": r["titulo"],
                "students": r["estudantes"],
                "advisor": r["orientador"],
                "about_text": r["about_text"],
            }
            for r in conn.execute("SELECT * FROM projeto ORDER BY ordem")
        ],
        "publications": [
            {
                "id": r["id"],
                "year": r["ano"],
                "title": r["titulo"],
                "participants": r["participantes"],
                "journal": r["periodico"],
                "doi_url": r["doi_url"],
            }
            for r in conn.execute("SELECT * FROM publicacao ORDER BY ordem")
        ],
        "contacts": [
            {
                "icon": r["icone"],
                "title": r["titulo"],
                "value": r["valor"],
                "subtitle": r["subtitulo"],
                "link": r["link"],
            }
            for r in conn.execute("SELECT * FROM contato ORDER BY ordem")
        ],
    }
    mensagens = [dict(r) for r in conn.execute("SELECT * FROM mensagem_contato ORDER BY id")]
    return conteudo, mensagens


def ler_conteudo_json(caminho: Path) -> dict | None:
    """Conteudo inicial a partir do antigo site_content.json (instalacao nova)."""
    if not caminho.exists():
        return None
    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    home = dados.get("home", {})
    about = home.get("about", {})
    hero = home.get("hero", {})
    projetos = dados.get("projects", {})
    publicacoes = dados.get("publications", {})
    equipe = dados.get("team", {})
    config = {
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
        "projects_page_title": projetos.get("page", {}).get("title", ""),
        "projects_page_subtitle": projetos.get("page", {}).get("subtitle", ""),
        "projects_section_title": projetos.get("page", {}).get("section_title", ""),
        "publications_page_title": publicacoes.get("page", {}).get("title", ""),
        "publications_page_subtitle": publicacoes.get("page", {}).get("subtitle", ""),
        "publications_section_title": publicacoes.get("page", {}).get("section_title", ""),
        "team_page_title": equipe.get("page", {}).get("title", ""),
        "team_page_subtitle": equipe.get("page", {}).get("subtitle", ""),
    }
    return {
        "config": config,
        "highlight": home.get("highlight", {}),
        "slider": about.get("slider", []),
        "partners": home.get("partners", []),
        "categories": equipe.get("categories", []),
        "members": equipe.get("members", []),
        "projects": projetos.get("items", []),
        "publications": publicacoes.get("items", []),
        "contacts": dados.get("contact", {}).get("items", []),
    }


def _limpo(valor) -> str | None:
    texto = v.texto_ou_nulo(valor)
    return None if texto in _PLACEHOLDERS else texto


def _gravar(avisos: list[str], rotulo: str, funcao, dados: dict, *args, **kwargs):
    """Grava o registro; campos opcionais invalidos sao descartados e reportados."""
    for _tentativa in range(3):
        try:
            return funcao(dados, *args, **kwargs)
        except ValidacaoErro as exc:
            descartaveis = [c for c in exc.campos if c in dados and c not in ("nome", "titulo", "ano", "modalidade", "categoria_id")]
            if not descartaveis:
                avisos.append(f"{rotulo}: nao migrado ({'; '.join(exc.mensagens())}).")
                return None
            for campo in descartaveis:
                avisos.append(f"{rotulo}: campo '{campo}' descartado ({exc.campos[campo]}) valor={dados[campo]!r}.")
                dados[campo] = None
        except ErroDominio as exc:
            avisos.append(f"{rotulo}: nao migrado ({exc.mensagem}).")
            return None
    return None


def _modalidade_e_periodo(badge: str | None) -> tuple[str, int | None, int | None]:
    texto = (badge or "").strip()
    anos = [int(a) for a in re.findall(r"(?:19|20)\d{2}", texto)]
    inicio = anos[0] if anos else None
    fim = anos[1] if len(anos) > 1 else None
    maiusculo = texto.upper()
    if "PIBITI" in maiusculo:
        modalidade = "PIBITI"
    elif "PIBIC" in maiusculo:
        modalidade = "PIBIC"
    elif "TCC" in maiusculo:
        modalidade = "TCC"
    elif "EXTENS" in maiusculo:
        modalidade = "EXTENSAO"
    else:
        modalidade = "OUTRO"
    return modalidade, inicio, fim


def _tipo_contato(item: dict) -> str:
    link = (item.get("link") or "").lower()
    icone = (item.get("icon") or "").lower()
    if link.startswith("mailto:") or "envelope" in icone:
        return "email"
    if link.startswith("tel:") or "telephone" in icone or "phone" in icone:
        return "telefone"
    if "geo" in icone or "map" in icone:
        return "endereco"
    if any(rede in icone for rede in ("instagram", "linkedin", "facebook", "twitter", "youtube", "github")):
        return "rede_social"
    if link.startswith("http"):
        return "site"
    return "outro"


def semear(conn: sqlite3.Connection, conteudo: dict, mensagens: list[dict] | None = None) -> list[str]:
    """Popula um banco v2 vazio a partir do conteudo no formato legado."""
    avisos: list[str] = []

    repo.atualizar_configuracoes(
        conn, {c: conteudo.get("config", {}).get(c, "") for c in v.CHAVES_CONFIGURACAO}
    )

    for slide in conteudo.get("slider", []):
        if slide.get("image"):
            _gravar(avisos, f"slide {slide.get('id')}", lambda d: repo.criar_slider(conn, d, slide["image"]),
                    {"texto_alternativo": slide.get("alt") or "Imagem do laboratorio"})

    for parceiro in conteudo.get("partners", []):
        if parceiro.get("image"):
            _gravar(avisos, f"parceiro {parceiro.get('name')}",
                    lambda d: repo.criar_parceiro(conn, d, parceiro["image"]),
                    {"nome": parceiro.get("name"), "link": _limpo(parceiro.get("link"))})

    categorias: dict[str, int] = {}
    for categoria in conteudo.get("categories", []):
        criada = _gravar(avisos, f"categoria {categoria.get('id')}", lambda d: repo.criar_categoria(conn, d), {
            "slug": v.slugificar(categoria["id"]),
            "titulo": categoria.get("title") or categoria["id"],
            "mensagem_vazia": categoria.get("empty_message"),
        })
        if criada:
            categorias[categoria["id"]] = criada["id"]

    membros: dict[str, int] = {}
    for membro in conteudo.get("members", []):
        categoria_id = categorias.get(membro.get("category"))
        if categoria_id is None:
            avisos.append(f"membro {membro.get('name')}: sem categoria valida, nao migrado.")
            continue
        for campo in ("github_url", "lattes_url"):
            if (membro.get(campo) or "").strip() in _PLACEHOLDERS:
                avisos.append(f"membro {membro.get('name')}: {campo} de exemplo descartado ({membro[campo]!r}).")
        criado = _gravar(avisos, f"membro {membro.get('name')}",
                         lambda d: repo.criar_membro(conn, d, foto=_limpo(membro.get("image"))), {
            "categoria_id": categoria_id,
            "nome": membro.get("name"),
            "funcao": _limpo(membro.get("role")),
            "github_url": _limpo(membro.get("github_url")),
            "lattes_url": _limpo(membro.get("lattes_url")),
            "descricao": _limpo(membro.get("description")),
            "tags": membro.get("tags") or [],
        })
        if criado:
            membros[membro["id"]] = criado["id"]

    indice_nomes = {v.normalizar_nome(nome): mid for nome, mid in
                    ((m["nome"], m["id"]) for m in repo.listar_membros(conn))}

    projetos: dict[str, int] = {}
    for projeto in conteudo.get("projects", []):
        modalidade, inicio, fim = _modalidade_e_periodo(projeto.get("badge"))
        orientador_nome = _limpo(projeto.get("advisor"))
        orientador_id = indice_nomes.get(v.normalizar_nome(orientador_nome)) if orientador_nome else None
        if orientador_nome and orientador_id is None:
            avisos.append(f"projeto {projeto.get('title')}: orientador '{orientador_nome}' nao e membro; "
                          "cadastre-o na equipe e selecione-o no painel.")
        criado = _gravar(avisos, f"projeto {projeto.get('title')}", lambda d: repo.criar_projeto(conn, d), {
            "titulo": projeto.get("title"),
            "modalidade": modalidade,
            "ano_inicio": inicio,
            "ano_fim": fim,
            "descricao": _limpo(projeto.get("about_text")),
            "orientador_id": orientador_id,
            "participantes": projeto.get("students") or "",
        })
        if criado:
            projetos[projeto["id"]] = criado["id"]

    publicacoes: dict[str, int] = {}
    for publicacao in conteudo.get("publications", []):
        link = _limpo(publicacao.get("doi_url"))
        doi = v.normalizar_doi(link) if link and "doi.org/" in link.lower() else None
        veiculo = _limpo(publicacao.get("journal"))
        criada = _gravar(avisos, f"publicacao {publicacao.get('title')}", lambda d: repo.criar_publicacao(conn, d), {
            "titulo": publicacao.get("title"),
            "ano": publicacao.get("year"),
            "tipo": "anais" if veiculo and "proceedings" in veiculo.lower() else "artigo",
            "veiculo": veiculo,
            "doi": doi,
            "url": None if doi else link,
            "autores": publicacao.get("participants") or "",
        })
        if criada:
            publicacoes[publicacao["id"]] = criada["id"]

    for contato in conteudo.get("contacts", []):
        _gravar(avisos, f"contato {contato.get('title')}", lambda d: repo.criar_contato(conn, d), {
            "tipo": _tipo_contato(contato),
            "titulo": contato.get("title"),
            "valor": contato.get("value"),
            "subtitulo": _limpo(contato.get("subtitle")),
            "link": _limpo(contato.get("link")),
            "icone": _limpo(contato.get("icon")),
        })

    destaque = conteudo.get("highlight") or {}
    alvo = destaque.get("item_id")
    if destaque.get("type") == "project" and alvo in projetos:
        repo.definir_destaque(conn, {"tipo": "projeto", "item_id": projetos[alvo]})
    elif destaque.get("type") == "publication" and alvo in publicacoes:
        repo.definir_destaque(conn, {"tipo": "publicacao", "item_id": publicacoes[alvo]})

    for mensagem in mensagens or []:
        try:
            with repo.transacao(conn):
                conn.execute(
                    "INSERT INTO mensagem_contato (nome_remetente, email_remetente, mensagem, lida, recebida_em) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (mensagem["nome"], mensagem["email"], mensagem["mensagem"],
                     1 if mensagem.get("lido") else 0, mensagem["enviado_em"]),
                )
        except ErroDominio as exc:
            avisos.append(f"mensagem {mensagem.get('id')}: nao migrada ({exc.mensagem}).")

    return avisos
