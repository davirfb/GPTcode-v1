"""Aplicacao Flask do site GPTcode: paginas publicas, painel e links de submissao.

A API REST fica em backend/api.py e as regras de dados em backend/repositorio.py.
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

if __package__ in (None, ""):  # execucao direta: python backend/app.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from backend import repositorio as repo
from backend import validadores as v
from backend.api import api, url_do_link
from backend.auth import (
    ADMIN_AUTH_COOKIE_NAME,
    admin_required,
    carregar_usuario,
    encerrar_sessao,
    get_admin_allowed_emails,
    get_firebase_client_config,
    get_firebase_setup_issues,
)
from backend.contexto import fechar_db, get_db, usuario_id
from backend.database import init_db
from backend.erros import ErroDominio, ValidacaoErro
from backend.mailer import send_notification
from backend.uploads import apagar_imagem, salvar_imagem

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / "static"),
    template_folder=str(FRONTEND_DIR / "templates"),
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "gptcode-admin-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.json.sort_keys = False
app.json.ensure_ascii = False

app.register_blueprint(api)
app.before_request(carregar_usuario)
app.teardown_appcontext(fechar_db)

for aviso in init_db():
    app.logger.warning("migracao do banco: %s", aviso)


# ---------------------------------------------------------------------------
# Filtros e contexto dos templates
# ---------------------------------------------------------------------------

@app.template_filter("lista_nomes")
def lista_nomes(nomes) -> str:
    """['A', 'B', 'C'] -> 'A, B e C'."""
    nomes = [n for n in nomes if n]
    if len(nomes) <= 1:
        return "".join(nomes)
    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


@app.context_processor
def contexto_templates():
    contexto = {
        "admin_logged_in": bool(getattr(g, "admin_user", None)),
        "rotulos": {
            "modalidades": v.MODALIDADE_ROTULO,
            "status_projeto": v.STATUS_PROJETO_ROTULO,
            "tipos_publicacao": v.TIPO_PUBLICACAO_ROTULO,
            "tipos_contato": v.TIPO_CONTATO_ROTULO,
            "papeis": v.PAPEIS_PARTICIPANTE,
        },
    }
    if request.path.startswith("/admin"):
        issues = get_firebase_setup_issues()
        contexto.update(
            firebase_config=get_firebase_client_config(),
            firebase_ready=not issues,
            firebase_setup_issues=issues,
            pending_count=repo.contar_submissoes_pendentes(get_db()) if contexto["admin_logged_in"] else 0,
            unread_messages_count=repo.contar_mensagens_nao_lidas(get_db()) if contexto["admin_logged_in"] else 0,
        )
    return contexto


@app.errorhandler(HTTPException)
def erro_http(exc: HTTPException):
    if request.path.startswith("/api/"):
        return jsonify({"erro": exc.description or exc.name}), exc.code
    return exc


# ---------------------------------------------------------------------------
# Paginas publicas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    return render_template(
        "index.html",
        cfg=repo.obter_configuracoes(db),
        slider=repo.listar_slider(db),
        parceiros=repo.listar_parceiros(db),
        destaque=repo.obter_destaque(db),
    )


@app.route("/contato", methods=["GET", "POST"])
def contato():
    db = get_db()
    enviado = {}
    erros = {}
    if request.method == "POST":
        enviado = {
            "nome_remetente": request.form.get("nome"),
            "email_remetente": request.form.get("email"),
            "assunto": request.form.get("assunto"),
            "mensagem": request.form.get("mensagem"),
        }
        try:
            repo.criar_mensagem(db, enviado)
        except ValidacaoErro as exc:
            erros = exc.campos
            flash("Revise os campos destacados.", "danger")
        else:
            flash("Mensagem enviada com sucesso!", "success")
            return redirect(url_for("contato"))
    return render_template(
        "contato.html",
        contatos=repo.listar_contatos(db),
        enviado=enviado,
        erros=erros,
    ), (422 if erros else 200)


@app.route("/equipe")
def equipe():
    db = get_db()
    membros = repo.listar_membros(db, apenas_ativos=True)
    secoes = [
        {**categoria, "membros": [m for m in membros if m["categoria_id"] == categoria["id"]]}
        for categoria in repo.listar_categorias(db)
    ]
    return render_template("equipe.html", cfg=repo.obter_configuracoes(db), secoes=secoes, total=len(membros))


@app.route("/publicacoes")
def publicacoes():
    db = get_db()
    return render_template("publicacoes.html", cfg=repo.obter_configuracoes(db), publicacoes=repo.listar_publicacoes(db))


@app.route("/projetos")
def projetos():
    db = get_db()
    return render_template("projetos.html", cfg=repo.obter_configuracoes(db), projetos=repo.listar_projetos(db))


# ---------------------------------------------------------------------------
# Formularios: conversao registro <-> campos do formulario
# ---------------------------------------------------------------------------

def _sem_nulos(dados: dict) -> dict:
    return {chave: ("" if valor is None else valor) for chave, valor in dados.items()}


def form_membro(membro: dict | None) -> dict:
    if not membro:
        return {"ativo": True}
    return _sem_nulos(
        {
            "categoria_id": membro["categoria_id"],
            "nome": membro["nome"],
            "funcao": membro["funcao"],
            "email": membro["email"],
            "github_url": membro["github_url"],
            "lattes_url": membro["lattes_url"],
            "descricao": membro["descricao"],
            "tags": ", ".join(membro["tags"]),
            "ativo": membro["ativo"],
        }
    )


def form_projeto(projeto: dict | None) -> dict:
    if not projeto:
        return {"status": "em_andamento"}
    linhas = [p["nome"] if p["papel"] == "estudante" else f"{p['nome']} ({p['papel']})" for p in projeto["participantes"]]
    return _sem_nulos(
        {
            "titulo": projeto["titulo"],
            "modalidade": projeto["modalidade"],
            "status": projeto["status"],
            "ano_inicio": projeto["ano_inicio"],
            "ano_fim": projeto["ano_fim"],
            "orientador_id": projeto["orientador_id"],
            "participantes": "\n".join(linhas),
            "descricao": projeto["descricao"],
        }
    )


def form_publicacao(publicacao: dict | None) -> dict:
    if not publicacao:
        return {"tipo": "artigo"}
    return _sem_nulos(
        {
            "titulo": publicacao["titulo"],
            "ano": publicacao["ano"],
            "tipo": publicacao["tipo"],
            "veiculo": publicacao["veiculo"],
            "autores": "\n".join(a["nome_citacao"] for a in publicacao["autores"]),
            "doi": publicacao["doi"],
            "url": publicacao["url"],
            "projeto_id": publicacao["projeto_id"],
        }
    )


def form_contato(contato_item: dict | None) -> dict:
    if not contato_item:
        return {"tipo": "email"}
    return _sem_nulos({c: contato_item[c] for c in ("tipo", "titulo", "valor", "subtitulo", "link", "icone")})


def _rascunho() -> dict:
    dados = request.form.to_dict()
    dados["ativo"] = "ativo" in request.form
    return dados


def _forms(itens: list[dict], prefixo: str, conversor, rascunhos: dict | None) -> dict:
    forms = {f"{prefixo}-{item['id']}": conversor(item) for item in itens}
    forms[f"{prefixo}-novo"] = conversor(None)
    forms.update(rascunhos or {})
    return forms


def _salvar(chave: str, pagina, destino: str, acao, sucesso: str):
    """Executa a acao; em erro, reapresenta a pagina com o que foi digitado."""
    try:
        acao()
    except ErroDominio as exc:
        for mensagem in exc.mensagens():
            flash(mensagem, "danger")
        return pagina({chave: _rascunho()}), exc.status_http
    flash(sucesso, "success")
    return redirect(destino)


# ---------------------------------------------------------------------------
# Painel: login, dashboard e configuracoes gerais
# ---------------------------------------------------------------------------

@app.route("/admin/login")
def admin_login():
    if request.args.get("encerrar"):
        encerrar_sessao()
        g.admin_user = None
    elif getattr(g, "admin_user", None):
        return redirect(url_for("admin_dashboard"))
    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("Sessao encerrada com sucesso.", "success")
    response = redirect(url_for("admin_login"))
    response.delete_cookie(ADMIN_AUTH_COOKIE_NAME, path="/")
    return response


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    return render_template(
        "admin/dashboard.html",
        stats=repo.estatisticas(db),
        cfg=repo.obter_configuracoes(db),
    )


@app.route("/admin/configuracoes", methods=["POST"])
@admin_required
def admin_update_settings():
    dados = {chave: valor for chave, valor in request.form.items() if chave in v.CHAVES_CONFIGURACAO}
    return _salvar(
        "configuracoes",
        pagina_admin_home,
        _voltar(url_for("admin_home")),
        lambda: repo.atualizar_configuracoes(get_db(), dados, usuario_id()),
        "Textos atualizados.",
    )


def _voltar(padrao: str) -> str:
    destino = request.form.get("voltar") or ""
    return destino if destino.startswith("/admin") else padrao


# ---------------------------------------------------------------------------
# Painel: pagina inicial (slider, destaque, parceiros)
# ---------------------------------------------------------------------------

def pagina_admin_home(rascunhos: dict | None = None):
    db = get_db()
    cfg = repo.obter_configuracoes(db)
    if rascunhos and "configuracoes" in rascunhos:
        cfg.update({k: val for k, val in rascunhos["configuracoes"].items() if k in cfg})
    return render_template(
        "admin/home.html",
        cfg=cfg,
        slider=repo.listar_slider(db),
        parceiros=repo.listar_parceiros(db),
        destaque=repo.obter_destaque(db),
        projetos=repo.listar_projetos(db),
        publicacoes=repo.listar_publicacoes(db),
    )


@app.route("/admin/home")
@admin_required
def admin_home():
    return pagina_admin_home()


@app.route("/admin/home/highlight", methods=["POST"])
@admin_required
def admin_update_highlight():
    selecao = request.form.get("highlight_selection", "nenhum")
    tipo, _, item_id = selecao.partition(":")
    return _salvar(
        "destaque",
        pagina_admin_home,
        url_for("admin_home"),
        lambda: repo.definir_destaque(get_db(), {"tipo": tipo, "item_id": item_id or None}),
        "Destaque principal atualizado.",
    )


def _com_imagem(campo: str, pasta: str, acao, obrigatoria: bool):
    """Salva o upload, executa a acao e desfaz o arquivo se a acao falhar."""
    def executar():
        imagem = salvar_imagem(request.files.get(campo), pasta, campo)
        if obrigatoria and not imagem:
            raise ValidacaoErro({campo: "Selecione uma imagem."})
        try:
            antiga = acao(imagem)
        except ErroDominio:
            apagar_imagem(imagem)
            raise
        apagar_imagem(antiga)
    return executar


@app.route("/admin/home/slider/add", methods=["POST"])
@admin_required
def admin_add_slider_image():
    dados = request.form.to_dict()
    return _salvar(
        "slide-novo",
        pagina_admin_home,
        url_for("admin_home") + "#slider",
        _com_imagem("imagem", "about-slider", lambda img: repo.criar_slider(get_db(), dados, img) and None, True),
        "Imagem adicionada ao slider.",
    )


@app.route("/admin/home/slider/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_slider_image(item_id: int):
    dados = request.form.to_dict()
    return _salvar(
        f"slide-{item_id}",
        pagina_admin_home,
        url_for("admin_home") + "#slider",
        _com_imagem("imagem", "about-slider",
                    lambda img: repo.atualizar_slider(get_db(), item_id, dados, img)[1], False),
        "Imagem do slider atualizada.",
    )


@app.route("/admin/home/slider/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_slider_image(item_id: int):
    return _salvar(
        f"slide-{item_id}",
        pagina_admin_home,
        url_for("admin_home") + "#slider",
        lambda: apagar_imagem(repo.remover_slider(get_db(), item_id)["imagem"]),
        "Imagem removida do slider.",
    )


@app.route("/admin/home/partners/add", methods=["POST"])
@admin_required
def admin_add_partner():
    dados = request.form.to_dict()
    return _salvar(
        "parceiro-novo",
        pagina_admin_home,
        url_for("admin_home") + "#parceiros",
        _com_imagem("logo", "partners", lambda img: repo.criar_parceiro(get_db(), dados, img) and None, True),
        "Parceiro ou apoiador adicionado.",
    )


@app.route("/admin/home/partners/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_partner(item_id: int):
    dados = request.form.to_dict()
    return _salvar(
        f"parceiro-{item_id}",
        pagina_admin_home,
        url_for("admin_home") + "#parceiros",
        _com_imagem("logo", "partners", lambda img: repo.atualizar_parceiro(get_db(), item_id, dados, img)[1], False),
        "Parceiro atualizado.",
    )


@app.route("/admin/home/partners/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_partner(item_id: int):
    return _salvar(
        f"parceiro-{item_id}",
        pagina_admin_home,
        url_for("admin_home") + "#parceiros",
        lambda: apagar_imagem(repo.remover_parceiro(get_db(), item_id)["logo"]),
        "Parceiro removido.",
    )


# ---------------------------------------------------------------------------
# Painel: projetos
# ---------------------------------------------------------------------------

def pagina_admin_projetos(rascunhos: dict | None = None):
    db = get_db()
    projetos_lista = repo.listar_projetos(db)
    return render_template(
        "admin/projects.html",
        projetos=projetos_lista,
        forms=_forms(projetos_lista, "projeto", form_projeto, rascunhos),
        membros=repo.listar_membros(db),
    )


@app.route("/admin/projects")
@admin_required
def admin_projects():
    return pagina_admin_projetos()


@app.route("/admin/projects/add", methods=["POST"])
@admin_required
def admin_add_project():
    return _salvar(
        "projeto-novo",
        pagina_admin_projetos,
        url_for("admin_projects"),
        lambda: repo.criar_projeto(get_db(), request.form.to_dict(), usuario_id()),
        "Projeto adicionado com sucesso.",
    )


@app.route("/admin/projects/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_project(item_id: int):
    return _salvar(
        f"projeto-{item_id}",
        pagina_admin_projetos,
        url_for("admin_projects") + f"#projeto-{item_id}",
        lambda: repo.atualizar_projeto(get_db(), item_id, request.form.to_dict(), usuario_id()),
        "Projeto atualizado.",
    )


@app.route("/admin/projects/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_project(item_id: int):
    return _salvar(
        f"projeto-{item_id}",
        pagina_admin_projetos,
        url_for("admin_projects"),
        lambda: repo.remover_projeto(get_db(), item_id),
        "Projeto removido.",
    )


# ---------------------------------------------------------------------------
# Painel: publicacoes
# ---------------------------------------------------------------------------

def pagina_admin_publicacoes(rascunhos: dict | None = None):
    db = get_db()
    publicacoes_lista = repo.listar_publicacoes(db)
    return render_template(
        "admin/publications.html",
        publicacoes=publicacoes_lista,
        forms=_forms(publicacoes_lista, "publicacao", form_publicacao, rascunhos),
        projetos=repo.listar_projetos(db),
    )


@app.route("/admin/publications")
@admin_required
def admin_publications():
    return pagina_admin_publicacoes()


@app.route("/admin/publications/add", methods=["POST"])
@admin_required
def admin_add_publication():
    return _salvar(
        "publicacao-novo",
        pagina_admin_publicacoes,
        url_for("admin_publications"),
        lambda: repo.criar_publicacao(get_db(), request.form.to_dict(), usuario_id()),
        "Publicacao adicionada com sucesso.",
    )


@app.route("/admin/publications/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_publication(item_id: int):
    return _salvar(
        f"publicacao-{item_id}",
        pagina_admin_publicacoes,
        url_for("admin_publications") + f"#publicacao-{item_id}",
        lambda: repo.atualizar_publicacao(get_db(), item_id, request.form.to_dict(), usuario_id()),
        "Publicacao atualizada.",
    )


@app.route("/admin/publications/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_publication(item_id: int):
    return _salvar(
        f"publicacao-{item_id}",
        pagina_admin_publicacoes,
        url_for("admin_publications"),
        lambda: repo.remover_publicacao(get_db(), item_id),
        "Publicacao removida.",
    )


# ---------------------------------------------------------------------------
# Painel: equipe (categorias e membros)
# ---------------------------------------------------------------------------

def pagina_admin_equipe(rascunhos: dict | None = None):
    db = get_db()
    membros = repo.listar_membros(db)
    categorias = repo.listar_categorias(db)
    secoes = [{**c, "membros": [m for m in membros if m["categoria_id"] == c["id"]]} for c in categorias]
    forms = _forms(membros, "membro", form_membro, rascunhos)
    for categoria in categorias:
        forms.setdefault(f"categoria-{categoria['id']}", _sem_nulos(categoria))
    forms.setdefault("categoria-novo", {})
    return render_template(
        "admin/team.html",
        membros=membros,
        categorias=categorias,
        secoes=secoes,
        forms=forms,
    )


@app.route("/admin/team")
@admin_required
def admin_team():
    return pagina_admin_equipe()


@app.route("/admin/team/categories/add", methods=["POST"])
@admin_required
def admin_add_team_category():
    return _salvar(
        "categoria-novo",
        pagina_admin_equipe,
        url_for("admin_team") + "#categorias",
        lambda: repo.criar_categoria(get_db(), request.form.to_dict()),
        "Categoria criada.",
    )


@app.route("/admin/team/categories/<int:category_id>/update", methods=["POST"])
@admin_required
def admin_update_team_category(category_id: int):
    return _salvar(
        f"categoria-{category_id}",
        pagina_admin_equipe,
        url_for("admin_team") + "#categorias",
        lambda: repo.atualizar_categoria(get_db(), category_id, request.form.to_dict(), parcial=True),
        "Categoria atualizada.",
    )


@app.route("/admin/team/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def admin_delete_team_category(category_id: int):
    return _salvar(
        f"categoria-{category_id}",
        pagina_admin_equipe,
        url_for("admin_team") + "#categorias",
        lambda: repo.remover_categoria(get_db(), category_id),
        "Categoria removida.",
    )


def _dados_membro() -> dict:
    dados = request.form.to_dict()
    dados["ativo"] = "ativo" in request.form
    return dados


@app.route("/admin/team/members/add", methods=["POST"])
@admin_required
def admin_add_team_member():
    dados = _dados_membro()
    return _salvar(
        "membro-novo",
        pagina_admin_equipe,
        url_for("admin_team") + "#membros",
        _com_imagem("foto", "team", lambda img: repo.criar_membro(get_db(), dados, usuario_id(), foto=img) and None, False),
        "Membro adicionado com sucesso.",
    )


@app.route("/admin/team/members/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_team_member(item_id: int):
    dados = _dados_membro()
    db = get_db()

    def acao(img):
        antiga = repo.obter_membro(db, item_id)["foto"] if img else None
        repo.atualizar_membro(db, item_id, dados, usuario_id(), foto=img)
        return antiga

    return _salvar(
        f"membro-{item_id}",
        pagina_admin_equipe,
        url_for("admin_team") + f"#membro-{item_id}",
        _com_imagem("foto", "team", acao, False),
        "Membro atualizado com sucesso.",
    )


@app.route("/admin/team/members/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_team_member(item_id: int):
    return _salvar(
        f"membro-{item_id}",
        pagina_admin_equipe,
        url_for("admin_team") + "#membros",
        lambda: apagar_imagem(repo.remover_membro(get_db(), item_id)["foto"]),
        "Membro removido com sucesso.",
    )


# ---------------------------------------------------------------------------
# Painel: contato e mensagens
# ---------------------------------------------------------------------------

def pagina_admin_contato(rascunhos: dict | None = None):
    contatos = repo.listar_contatos(get_db())
    return render_template(
        "admin/contact.html",
        contatos=contatos,
        forms=_forms(contatos, "contato", form_contato, rascunhos),
    )


@app.route("/admin/contato")
@admin_required
def admin_contact():
    return pagina_admin_contato()


@app.route("/admin/contato/add", methods=["POST"])
@admin_required
def admin_add_contact():
    return _salvar(
        "contato-novo",
        pagina_admin_contato,
        url_for("admin_contact"),
        lambda: repo.criar_contato(get_db(), request.form.to_dict(), usuario_id()),
        "Forma de contato adicionada com sucesso.",
    )


@app.route("/admin/contato/<int:item_id>/update", methods=["POST"])
@admin_required
def admin_update_contact(item_id: int):
    return _salvar(
        f"contato-{item_id}",
        pagina_admin_contato,
        url_for("admin_contact"),
        lambda: repo.atualizar_contato(get_db(), item_id, request.form.to_dict(), usuario_id()),
        "Forma de contato atualizada.",
    )


@app.route("/admin/contato/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_contact(item_id: int):
    return _salvar(
        f"contato-{item_id}",
        pagina_admin_contato,
        url_for("admin_contact"),
        lambda: repo.remover_contato(get_db(), item_id),
        "Forma de contato removida.",
    )


@app.route("/admin/mensagens")
@admin_required
def admin_mensagens():
    apenas_nao_lidas = request.args.get("filtro") == "nao_lidas"
    return render_template(
        "admin/mensagens.html",
        mensagens=repo.listar_mensagens(get_db(), apenas_nao_lidas=apenas_nao_lidas),
        apenas_nao_lidas=apenas_nao_lidas,
    )


@app.route("/admin/mensagens/<int:mensagem_id>/marcar-lida", methods=["POST"])
@admin_required
def admin_marcar_mensagem_lida(mensagem_id: int):
    lida = request.form.get("lida", "1") == "1"
    try:
        repo.marcar_mensagem(get_db(), mensagem_id, lida)
    except ErroDominio as exc:
        flash(exc.mensagem, "danger")
    return redirect(url_for("admin_mensagens", filtro=request.args.get("filtro")))


@app.route("/admin/mensagens/<int:mensagem_id>/delete", methods=["POST"])
@admin_required
def admin_remover_mensagem(mensagem_id: int):
    try:
        repo.remover_mensagem(get_db(), mensagem_id)
        flash("Mensagem removida.", "success")
    except ErroDominio as exc:
        flash(exc.mensagem, "danger")
    return redirect(url_for("admin_mensagens", filtro=request.args.get("filtro")))


# ---------------------------------------------------------------------------
# Links de uso unico (gerados no painel) e submissoes pendentes
# ---------------------------------------------------------------------------

@app.route("/admin/links", methods=["POST"])
@admin_required
def admin_gerar_link():
    # sem ancora: o link gerado aparece no topo da pagina e precisa ficar visivel
    destino = _voltar(url_for("admin_pending")).split("#", 1)[0]
    dados = {chave: request.form.get(chave) for chave in ("recurso", "acao", "item_id", "validade_dias")}
    try:
        link = repo.gerar_link(get_db(), dados, usuario_id())
    except ErroDominio as exc:
        for mensagem in exc.mensagens():
            flash(mensagem, "danger")
    else:
        flash(url_do_link(link), "generated_link")
    return redirect(destino)


@app.route("/admin/links/<int:link_id>/delete", methods=["POST"])
@admin_required
def admin_revogar_link(link_id: int):
    try:
        repo.revogar_link(get_db(), link_id)
        flash("Link revogado.", "success")
    except ErroDominio as exc:
        flash(exc.mensagem, "danger")
    return redirect(url_for("admin_pending") + "#links")


def resumo_submissao(db, recurso: str, dados: dict | None) -> list[tuple[str, str]]:
    """Campos legiveis (rotulo, valor) de uma submissao ou de um registro atual."""
    if not dados:
        return []
    nomes_membros = {m["id"]: m["nome"] for m in repo.listar_membros(db)}
    if recurso == "membro":
        categorias = {c["id"]: c["titulo"] for c in repo.listar_categorias(db)}
        campos = [
            ("Categoria", categorias.get(dados.get("categoria_id"), "")),
            ("Nome", dados.get("nome")),
            ("Funcao", dados.get("funcao")),
            ("E-mail", dados.get("email")),
            ("GitHub", dados.get("github_url")),
            ("Lattes", dados.get("lattes_url")),
            ("Descricao", dados.get("descricao")),
            ("Tags", ", ".join(dados.get("tags") or [])),
            ("Foto", "nova foto enviada" if dados.get("foto") else ""),
        ]
    elif recurso == "projeto":
        participantes = [
            nomes_membros.get(p.get("membro_id"), p.get("nome") or "") + ("" if p.get("papel", "estudante") == "estudante" else f" ({p['papel']})")
            for p in dados.get("participantes") or []
        ]
        campos = [
            ("Titulo", dados.get("titulo")),
            ("Modalidade", v.MODALIDADE_ROTULO.get(dados.get("modalidade"), dados.get("modalidade"))),
            ("Situacao", v.STATUS_PROJETO_ROTULO.get(dados.get("status"), dados.get("status"))),
            ("Ano de inicio", dados.get("ano_inicio")),
            ("Ano de termino", dados.get("ano_fim")),
            ("Orientador", nomes_membros.get(dados.get("orientador_id"), "")),
            ("Participantes", ", ".join(participantes)),
            ("Descricao", dados.get("descricao")),
        ]
    else:
        projetos_titulos = {p["id"]: p["titulo"] for p in repo.listar_projetos(db)}
        campos = [
            ("Titulo", dados.get("titulo")),
            ("Ano", dados.get("ano")),
            ("Tipo", v.TIPO_PUBLICACAO_ROTULO.get(dados.get("tipo"), dados.get("tipo"))),
            ("Veiculo", dados.get("veiculo")),
            ("Autores", "; ".join(a.get("nome_citacao") or a.get("nome") or "" for a in dados.get("autores") or [])),
            ("DOI", dados.get("doi")),
            ("Link", dados.get("url")),
            ("Projeto", projetos_titulos.get(dados.get("projeto_id"), "")),
        ]
    return [(rotulo, "" if valor is None else str(valor)) for rotulo, valor in campos]


_ENTRADA = {
    "membro": repo.membro_para_entrada,
    "projeto": repo.projeto_para_entrada,
    "publicacao": repo.publicacao_para_entrada,
}


@app.route("/admin/pending")
@admin_required
def admin_pending():
    db = get_db()
    submissoes = []
    for submissao in repo.listar_submissoes(db, "pendente"):
        atual = _ENTRADA[submissao["recurso"]](submissao["atual"]) if submissao["atual"] else None
        submissoes.append(
            {
                **submissao,
                "campos": resumo_submissao(db, submissao["recurso"], submissao["dados"]),
                "campos_atuais": resumo_submissao(db, submissao["recurso"], atual),
            }
        )
    return render_template(
        "admin/pending.html",
        submissoes=submissoes,
        historico=repo.listar_submissoes(db, None)[:15],
        links=repo.listar_links(db, apenas_ativos=True),
    )


@app.route("/admin/pending/<int:submission_id>/approve", methods=["POST"])
@admin_required
def admin_approve_submission(submission_id: int):
    try:
        repo.aprovar_submissao(get_db(), submission_id, usuario_id())
        flash("Submissao aprovada e publicada no site.", "success")
    except ErroDominio as exc:
        flash("Nao foi possivel aprovar: " + " ".join(exc.mensagens()), "danger")
    return redirect(url_for("admin_pending"))


@app.route("/admin/pending/<int:submission_id>/reject", methods=["POST"])
@admin_required
def admin_reject_submission(submission_id: int):
    try:
        submissao = repo.rejeitar_submissao(get_db(), submission_id, usuario_id())
        apagar_imagem(submissao["dados"].get("foto"))
        flash("Submissao rejeitada.", "warning")
    except ErroDominio as exc:
        flash(exc.mensagem, "danger")
    return redirect(url_for("admin_pending"))


# ---------------------------------------------------------------------------
# Formulario publico acessado pelo link de uso unico
# ---------------------------------------------------------------------------

_CAMPOS_SUBMISSAO = {
    "membro": ("categoria_id", "nome", "funcao", "email", "github_url", "lattes_url", "descricao", "tags"),
    "projeto": ("titulo", "modalidade", "status", "ano_inicio", "ano_fim", "orientador_id", "participantes", "descricao"),
    "publicacao": ("titulo", "ano", "tipo", "veiculo", "autores", "doi", "url", "projeto_id"),
}
_VALIDAR = {"membro": v.validar_membro, "projeto": v.validar_projeto, "publicacao": v.validar_publicacao}
_FORM = {"membro": form_membro, "projeto": form_projeto, "publicacao": form_publicacao}
_OBTER = {"membro": repo.obter_membro, "projeto": repo.obter_projeto, "publicacao": repo.obter_publicacao}
_ROTULO_RECURSO = {"membro": "Membro da equipe", "projeto": "Projeto", "publicacao": "Publicacao"}


@app.route("/submit/<recurso>/<token>", methods=["GET", "POST"])
def submit_resource(recurso: str, token: str):
    if recurso not in _CAMPOS_SUBMISSAO:
        abort(404)
    db = get_db()
    link = repo.validar_token(db, token, recurso)
    if not link:
        return render_template("submit/invalid.html"), 410

    atual = _OBTER[recurso](db, link["item_id"]) if link["acao"] == "editar" else None
    valores = _FORM[recurso](atual)
    erros: dict[str, str] = {}

    if request.method == "POST":
        entrada = {campo: request.form.get(campo) for campo in _CAMPOS_SUBMISSAO[recurso]}
        valores = _sem_nulos(entrada)
        foto = None
        try:
            validado = _VALIDAR[recurso](entrada)
            dados = {campo: validado[campo] for campo in _CAMPOS_SUBMISSAO[recurso]}
            repo.simular_submissao(db, recurso, link["acao"], link["item_id"], dados)
            if recurso == "membro":
                foto = salvar_imagem(request.files.get("foto"), "pending-team", "foto")
                if foto:
                    dados["foto"] = foto
            repo.registrar_submissao(db, link, dados)
        except ErroDominio as exc:
            apagar_imagem(foto)
            erros = exc.campos or {"_": exc.mensagem}
        else:
            send_notification(
                subject=f"Nova submissao pendente: {_ROTULO_RECURSO[recurso]}",
                body=(
                    "Uma nova submissao aguarda validacao no painel administrativo.\n\n"
                    f"Tipo: {_ROTULO_RECURSO[recurso]} ({link['acao']})\n"
                    f"Acesse: {url_for('admin_pending', _external=True)}"
                ),
                recipients=list(get_admin_allowed_emails()),
            )
            return render_template("submit/success.html")

    db_membros = repo.listar_membros(db) if recurso == "projeto" else []
    return render_template(
        f"submit/{recurso}.html",
        link=link,
        f=valores,
        erros=erros,
        categorias=repo.listar_categorias(db) if recurso == "membro" else [],
        membros=db_membros,
        projetos=repo.listar_projetos(db) if recurso == "publicacao" else [],
    ), (422 if erros else 200)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
