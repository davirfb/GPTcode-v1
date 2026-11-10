"""Aplicacao Flask do site GPTcode: paginas publicas, painel e links de submissao.

A API REST fica em backend/api.py e as regras de dados em backend/repositorio.py.
"""

from __future__ import annotations

import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

if __package__ in (None, ""):  # execucao direta: python backend/app.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import IntegerConverter

from backend import repositorio as repo
from backend import validadores as v
from backend.api import api
from backend.auth import (
    COOKIE_FIREBASE,
    carregar_usuario,
    csrf_campo,
    csrf_token,
    csrf_valido,
    encerrar_sessao,
    get_firebase_client_config,
    get_firebase_setup_issues,
    login_required,
    proximo_seguro,
    sair,
)
from backend.contexto import fechar_db, get_db, url_do_link, url_externa, usuario_id
from backend.database import init_db
from backend.erros import ErroDominio, ValidacaoErro, rotulo_campo
from backend.mailer import enviar_aviso
from backend.uploads import apagar_imagem, com_imagem

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / "static"),
    template_folder=str(FRONTEND_DIR / "templates"),
)
# A chave assina o cookie de sessão (que identifica o usuário logado). Nunca usar
# um valor fixo do código: sem a variável, gera uma chave aleatória por execução.
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "").strip() or secrets.token_hex(32)
if not os.getenv("FLASK_SECRET_KEY", "").strip():
    app.logger.warning("FLASK_SECRET_KEY não definida: usando chave temporária (as sessões caem a cada reinício).")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

ATRAS_DE_PROXY = os.getenv("RENDER", "").lower() == "true" or os.getenv("ATRAS_DE_PROXY", "").lower() == "true"
if ATRAS_DE_PROXY:
    # IP real do visitante e esquema https vêm do proxy (1 salto). Só ligado atrás de
    # proxy: sem ele, qualquer um forjaria X-Forwarded-For para driblar o limite de tentativas.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.config["PREFERRED_URL_SCHEME"] = "https"

# O cookie de sessão só trafega por HTTPS, exceto quando DESENVOLVIMENTO=true (http://localhost).
app.config["SESSION_COOKIE_SECURE"] = os.getenv("DESENVOLVIMENTO", "").lower() != "true"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.json.sort_keys = False
app.json.ensure_ascii = False


class IdConverter(IntegerConverter):
    """<int:...> com teto no maior inteiro do SQLite: um id gigante vira 404 em vez de erro 500."""

    def __init__(self, url_map, *args, **kwargs):
        kwargs.setdefault("max", v.INTEIRO_MAXIMO)
        super().__init__(url_map, *args, **kwargs)


# precisa vir antes de registrar as rotas (inclusive as da API)
app.url_map.converters["int"] = IdConverter

app.register_blueprint(api)
app.before_request(carregar_usuario)


@app.after_request
def cabecalhos_de_seguranca(resposta):
    """Cabeçalhos de proteção em todas as respostas."""
    # o navegador respeita o tipo informado (um upload não vira página/script)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    # o site não pode ser carregado dentro de iframe de outro site (clickjacking)
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
    resposta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if ATRAS_DE_PROXY:  # produção, sempre por HTTPS
        resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return resposta
app.teardown_appcontext(fechar_db)

app.jinja_env.globals.update(csrf_campo=csrf_campo, csrf_token=csrf_token)

init_db()


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
        "admin_logged_in": bool(getattr(g, "usuario", None)),
        "rotulos": {
            "modalidades": v.MODALIDADE_ROTULO,
            "status_projeto": v.STATUS_PROJETO_ROTULO,
            "tipos_publicacao": v.TIPO_PUBLICACAO_ROTULO,
            "tipos_contato": v.TIPO_CONTATO_ROTULO,
            "papeis": v.PAPEIS_PARTICIPANTE,
        },
    }
    if request.path.startswith("/admin"):
        problemas = get_firebase_setup_issues()
        contexto.update(
            firebase_config=get_firebase_client_config(),
            firebase_ready=not problemas,
            firebase_setup_issues=problemas,
            usuario_atual=getattr(g, "usuario", None),
            pending_count=repo.contar_submissoes_pendentes(get_db()) if contexto["admin_logged_in"] else 0,
            unread_messages_count=repo.contar_mensagens_nao_lidas(get_db()) if contexto["admin_logged_in"] else 0,
            erros_form=getattr(g, "erros_form", {}),
        )
    return contexto


_ERROS_HTTP = {
    400: ("Requisição inválida", "Não foi possível processar o envio."),
    401: ("Acesso não autorizado", "Faça login para continuar."),
    403: ("Acesso negado", "Você não tem permissão para acessar esta página."),
    404: ("Página não encontrada", "O endereço acessado não existe ou foi removido."),
    405: ("Operação não permitida", "Esta página não aceita esse tipo de requisição."),
    410: ("Conteúdo indisponível", "Este conteúdo não está mais disponível."),
    413: ("Arquivo muito grande", "O envio ultrapassa o limite de 8 MB."),
}


def _descricao_propria(exc: HTTPException) -> str | None:
    """Mensagem definida pelo sistema em abort(...), e não a padrão (em inglês) do Werkzeug."""
    padrao = type(exc).description
    return exc.description if exc.description and exc.description != padrao else None


_CAMPOS_SECRETOS = {"csrf_token", "senha", "senha_atual", "nova_senha", "confirmacao"}


@app.errorhandler(HTTPException)
def erro_http(exc: HTTPException):
    titulo, mensagem = _ERROS_HTTP.get(exc.code, ("Erro", "Ocorreu um erro ao processar a requisição."))
    mensagem = _descricao_propria(exc) or mensagem
    if request.path.startswith("/api/"):
        return jsonify({"erro": mensagem}), exc.code
    rascunho = []
    if exc.code == 400 and request.method == "POST" and request.path.startswith("/admin"):
        # token CSRF vencido ou sessão encerrada em outro aparelho: devolve o que a pessoa digitou
        rascunho = [(rotulo_campo(campo), valor) for campo, valor in request.form.items()
                    if valor and campo not in _CAMPOS_SECRETOS and len(valor) <= 5000]
        if not getattr(g, "usuario", None):
            titulo = "Sessão encerrada"
            mensagem = "Sua sessão expirou ou foi encerrada em outro aparelho. Entre de novo e refaça o envio."
        if rascunho:
            mensagem += " O que você digitou está abaixo, para copiar."
    return render_template("erro.html", codigo=exc.code, titulo=titulo, mensagem=mensagem,
                           rascunho=rascunho), exc.code


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
    status = 200
    if request.method == "POST":
        enviado = {
            "nome_remetente": request.form.get("nome"),
            "email_remetente": request.form.get("email"),
            "assunto": request.form.get("assunto"),
            "mensagem": request.form.get("mensagem"),
        }
        if not csrf_valido():
            # página aberta há muito tempo ou envio vindo de outro site: mantém o texto digitado
            flash("O formulário expirou. Confira os dados e clique em Enviar novamente.", "warning")
            status = 400
        elif request.form.get("site"):
            # campo-isca invisível: só robôs o preenchem. Finge sucesso e não grava.
            flash("Mensagem enviada com sucesso!", "success")
            return redirect(url_for("contato"))
        else:
            try:
                repo.criar_mensagem(db, enviado, ip=request.remote_addr)
            except ValidacaoErro as exc:
                erros = exc.campos
                flash("Revise os campos destacados.", "danger")
                status = 422
            except ErroDominio as exc:
                flash(exc.mensagem, "danger")
                status = exc.status_http
            else:
                flash("Mensagem enviada com sucesso!", "success")
                return redirect(url_for("contato"))
    return render_template(
        "contato.html",
        contatos=repo.listar_contatos(db),
        enviado=enviado,
        erros=erros,
    ), status


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
        g.erros_form = {chave: exc.campos}  # destaca os campos errados no formulário certo
        return pagina({chave: _rascunho()}), exc.status_http
    if sucesso:
        flash(sucesso, "success")
    return redirect(destino)


def registrar_crud(base: str, *, chave: str, pagina, lista: str, nomes: tuple[str, str, str],
                   criar, atualizar, remover, mensagens: tuple[str, str, str],
                   ancora_lista: str = "", ancora_item: str | None = None,
                   imagem: tuple[str, str] | None = None, imagem_obrigatoria: bool = False,
                   parametro: str = "item_id", ler_form=None) -> None:
    """Registra as 3 rotas POST de um cadastro do painel, com as mesmas regras para todos:

        <base>/add                 -> criar(dados[, imagem])
        <base>/<id>/update         -> atualizar(item_id, dados[, imagem])
        <base>/<id>/delete         -> remover(item_id)

    Em erro, a página é reapresentada com o que foi digitado e os campos errados
    destacados (ver _salvar). Com `imagem=(campo, pasta)`, o upload é gravado e
    desfeito se a gravação falhar (uploads.com_imagem). `ancora_item` (ex.:
    "#projeto-{}") leva de volta ao item editado."""
    ler = ler_form or (lambda: request.form.to_dict())
    nome_add, nome_update, nome_delete = nomes
    msg_add, msg_update, msg_delete = mensagens

    def destino(item_id=None):
        if item_id is not None and ancora_item:
            return url_for(lista) + ancora_item.format(item_id)
        return url_for(lista) + ancora_lista

    def acao_com_imagem(funcao, obrigatoria):
        if imagem:
            return _com_imagem(imagem[0], imagem[1], funcao, obrigatoria)
        return lambda: funcao(None)

    def adicionar():
        dados = ler()
        acao = acao_com_imagem(lambda img: criar(dados, img) if imagem else criar(dados), imagem_obrigatoria)
        return _salvar(f"{chave}-novo", pagina, destino(), acao, msg_add)

    def alterar(**valores):
        item_id, dados = valores[parametro], ler()
        acao = acao_com_imagem(
            lambda img: atualizar(item_id, dados, img) if imagem else atualizar(item_id, dados), False)
        return _salvar(f"{chave}-{item_id}", pagina, destino(item_id), acao, msg_update)

    def excluir(**valores):
        item_id = valores[parametro]
        return _salvar(f"{chave}-{item_id}", pagina, destino(), lambda: remover(item_id), msg_delete)

    for regra, nome, funcao in (
        (f"{base}/add", nome_add, adicionar),
        (f"{base}/<int:{parametro}>/update", nome_update, alterar),
        (f"{base}/<int:{parametro}>/delete", nome_delete, excluir),
    ):
        funcao.__name__ = nome
        app.add_url_rule(regra, endpoint=nome, view_func=login_required(funcao), methods=["POST"])


# ---------------------------------------------------------------------------
# Painel: login, dashboard e configuracoes gerais
# ---------------------------------------------------------------------------

@app.route("/admin/login")
def admin_login():
    proximo = proximo_seguro(request.args.get("proximo"))
    if request.args.get("encerrar"):  # o Firebase recusou o acesso: volta ao formulário
        encerrar_sessao()
        g.usuario = None
    elif getattr(g, "usuario", None):
        return redirect(proximo or url_for("admin_dashboard"))
    return render_template("admin/login.html", proximo=proximo)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    sair()
    flash("Sessão encerrada com sucesso.", "success")
    resposta = redirect(url_for("admin_login"))
    resposta.delete_cookie(COOKIE_FIREBASE, path="/")
    return resposta


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    return render_template(
        "admin/dashboard.html",
        stats=repo.estatisticas(db),
        cfg=repo.obter_configuracoes(db),
    )


@app.route("/admin/configuracoes", methods=["POST"])
@login_required
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
        rascunhos=rascunhos or {},
    )


@app.route("/admin/home")
@login_required
def admin_home():
    return pagina_admin_home()


@app.route("/admin/home/highlight", methods=["POST"])
@login_required
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
    """Ação para _salvar: grava o upload e o desfaz se a ação falhar (ver uploads.com_imagem)."""
    return lambda: com_imagem(request.files.get(campo), pasta, campo, acao, obrigatoria)


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
@login_required
def admin_projects():
    return pagina_admin_projetos()


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
@login_required
def admin_publications():
    return pagina_admin_publicacoes()


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
@login_required
def admin_team():
    return pagina_admin_equipe()


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
@login_required
def admin_contact():
    return pagina_admin_contato()

# ---------------------------------------------------------------------------
# Painel: cadastros (todas as rotas incluir / atualizar / remover)
# ---------------------------------------------------------------------------

def _apagar(caminho: str | None) -> None:
    apagar_imagem(caminho)


registrar_crud(
    "/admin/home/slider", chave="slide", pagina=pagina_admin_home, lista="admin_home", ancora_lista="#slider",
    nomes=("admin_add_slider_image", "admin_update_slider_image", "admin_delete_slider_image"),
    imagem=("imagem", "about-slider"), imagem_obrigatoria=True,
    criar=lambda dados, img: repo.criar_slider(get_db(), dados, img),
    atualizar=lambda item_id, dados, img: repo.atualizar_slider(get_db(), item_id, dados, img),
    remover=lambda item_id: _apagar(repo.remover_slider(get_db(), item_id)["imagem"]),
    mensagens=("Imagem adicionada ao slider.", "Imagem do slider atualizada.", "Imagem removida do slider."),
)

registrar_crud(
    "/admin/home/partners", chave="parceiro", pagina=pagina_admin_home, lista="admin_home",
    ancora_lista="#parceiros",
    nomes=("admin_add_partner", "admin_update_partner", "admin_delete_partner"),
    imagem=("logo", "partners"), imagem_obrigatoria=True,
    criar=lambda dados, img: repo.criar_parceiro(get_db(), dados, img),
    atualizar=lambda item_id, dados, img: repo.atualizar_parceiro(get_db(), item_id, dados, img),
    remover=lambda item_id: _apagar(repo.remover_parceiro(get_db(), item_id)["logo"]),
    mensagens=("Parceiro ou apoiador adicionado.", "Parceiro atualizado.", "Parceiro removido."),
)

registrar_crud(
    "/admin/projects", chave="projeto", pagina=pagina_admin_projetos, lista="admin_projects",
    ancora_item="#projeto-{}",
    nomes=("admin_add_project", "admin_update_project", "admin_delete_project"),
    criar=lambda dados: repo.criar_projeto(get_db(), dados, usuario_id()),
    atualizar=lambda item_id, dados: repo.atualizar_projeto(get_db(), item_id, dados, usuario_id()),
    remover=lambda item_id: repo.remover_projeto(get_db(), item_id),
    mensagens=("Projeto adicionado com sucesso.", "Projeto atualizado.", "Projeto removido."),
)

registrar_crud(
    "/admin/publications", chave="publicacao", pagina=pagina_admin_publicacoes, lista="admin_publications",
    ancora_item="#publicacao-{}",
    nomes=("admin_add_publication", "admin_update_publication", "admin_delete_publication"),
    criar=lambda dados: repo.criar_publicacao(get_db(), dados, usuario_id()),
    atualizar=lambda item_id, dados: repo.atualizar_publicacao(get_db(), item_id, dados, usuario_id()),
    remover=lambda item_id: repo.remover_publicacao(get_db(), item_id),
    mensagens=("Publicação adicionada com sucesso.", "Publicação atualizada.", "Publicação removida."),
)

registrar_crud(
    "/admin/team/categories", chave="categoria", pagina=pagina_admin_equipe, lista="admin_team",
    ancora_lista="#categorias", parametro="category_id",
    nomes=("admin_add_team_category", "admin_update_team_category", "admin_delete_team_category"),
    criar=lambda dados: repo.criar_categoria(get_db(), dados),
    atualizar=lambda item_id, dados: repo.atualizar_categoria(get_db(), item_id, dados, parcial=True),
    remover=lambda item_id: repo.remover_categoria(get_db(), item_id),
    mensagens=("Categoria criada.", "Categoria atualizada.", "Categoria removida."),
)


def _atualizar_membro(item_id: int, dados: dict, foto: str | None) -> str | None:
    """Atualiza o membro e devolve a foto antiga (apagada só se a nova foi salva)."""
    db = get_db()
    antiga = repo.obter_membro(db, item_id)["foto"] if foto else None
    repo.atualizar_membro(db, item_id, dados, usuario_id(), foto=foto)
    return antiga


registrar_crud(
    "/admin/team/members", chave="membro", pagina=pagina_admin_equipe, lista="admin_team",
    ancora_lista="#membros", ancora_item="#membro-{}", ler_form=_rascunho,
    nomes=("admin_add_team_member", "admin_update_team_member", "admin_delete_team_member"),
    imagem=("foto", "team"),
    criar=lambda dados, img: repo.criar_membro(get_db(), dados, usuario_id(), foto=img),
    atualizar=_atualizar_membro,
    remover=lambda item_id: _apagar(repo.remover_membro(get_db(), item_id)["foto"]),
    mensagens=("Membro adicionado com sucesso.", "Membro atualizado com sucesso.", "Membro removido com sucesso."),
)

registrar_crud(
    "/admin/contato", chave="contato", pagina=pagina_admin_contato, lista="admin_contact",
    nomes=("admin_add_contact", "admin_update_contact", "admin_delete_contact"),
    criar=lambda dados: repo.criar_contato(get_db(), dados, usuario_id()),
    atualizar=lambda item_id, dados: repo.atualizar_contato(get_db(), item_id, dados, usuario_id()),
    remover=lambda item_id: repo.remover_contato(get_db(), item_id),
    mensagens=("Forma de contato adicionada com sucesso.", "Forma de contato atualizada.",
               "Forma de contato removida."),
)


def pagina_admin_mensagens(_rascunhos: dict | None = None):
    apenas_nao_lidas = request.args.get("filtro") == "nao_lidas"
    return render_template(
        "admin/mensagens.html",
        mensagens=repo.listar_mensagens(get_db(), apenas_nao_lidas=apenas_nao_lidas),
        apenas_nao_lidas=apenas_nao_lidas,
    )


@app.route("/admin/mensagens")
@login_required
def admin_mensagens():
    return pagina_admin_mensagens()


@app.route("/admin/mensagens/<int:mensagem_id>/marcar-lida", methods=["POST"])
@login_required
def admin_marcar_mensagem_lida(mensagem_id: int):
    lida = request.form.get("lida", "1") == "1"
    return _salvar("mensagem", pagina_admin_mensagens, url_for("admin_mensagens", filtro=request.args.get("filtro")),
                   lambda: repo.marcar_mensagem(get_db(), mensagem_id, lida), None)


@app.route("/admin/mensagens/<int:mensagem_id>/delete", methods=["POST"])
@login_required
def admin_remover_mensagem(mensagem_id: int):
    return _salvar("mensagem", pagina_admin_mensagens, url_for("admin_mensagens", filtro=request.args.get("filtro")),
                   lambda: repo.remover_mensagem(get_db(), mensagem_id), "Mensagem removida.")


# ---------------------------------------------------------------------------
# Links de uso unico (gerados no painel) e submissoes pendentes
# ---------------------------------------------------------------------------

@app.route("/admin/links", methods=["POST"])
@login_required
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


def _nomes_participantes(dados: dict, nomes_membros: dict) -> str:
    nomes = []
    for p in dados.get("participantes") or []:
        nome = nomes_membros.get(p.get("membro_id"), p.get("nome") or "")
        papel = p.get("papel", "estudante")
        nomes.append(nome if papel == "estudante" else f"{nome} ({papel})")
    return ", ".join(nomes)


def _nomes_autores(dados: dict) -> str:
    return "; ".join(a.get("nome_citacao") or a.get("nome") or "" for a in dados.get("autores") or [])


# Campos mostrados na tela de submissões pendentes: (rótulo, função que lê o valor).
# `ref` traz os nomes de categorias, membros e projetos para trocar ids por texto.
_RESUMO = {
    "membro": (
        ("Categoria", lambda d, ref: ref["categorias"].get(d.get("categoria_id"), "")),
        ("Nome", lambda d, ref: d.get("nome")),
        ("Função", lambda d, ref: d.get("funcao")),
        ("E-mail", lambda d, ref: d.get("email")),
        ("GitHub", lambda d, ref: d.get("github_url")),
        ("Lattes", lambda d, ref: d.get("lattes_url")),
        ("Descrição", lambda d, ref: d.get("descricao")),
        ("Tags", lambda d, ref: ", ".join(d.get("tags") or [])),
        ("Foto", lambda d, ref: "nova foto enviada" if d.get("foto") else ""),
    ),
    "projeto": (
        ("Título", lambda d, ref: d.get("titulo")),
        ("Modalidade", lambda d, ref: v.MODALIDADE_ROTULO.get(d.get("modalidade"), d.get("modalidade"))),
        ("Situação", lambda d, ref: v.STATUS_PROJETO_ROTULO.get(d.get("status"), d.get("status"))),
        ("Ano de início", lambda d, ref: d.get("ano_inicio")),
        ("Ano de término", lambda d, ref: d.get("ano_fim")),
        ("Orientador", lambda d, ref: ref["membros"].get(d.get("orientador_id"), "")),
        ("Participantes", lambda d, ref: _nomes_participantes(d, ref["membros"])),
        ("Descrição", lambda d, ref: d.get("descricao")),
    ),
    "publicacao": (
        ("Título", lambda d, ref: d.get("titulo")),
        ("Ano", lambda d, ref: d.get("ano")),
        ("Tipo", lambda d, ref: v.TIPO_PUBLICACAO_ROTULO.get(d.get("tipo"), d.get("tipo"))),
        ("Veículo", lambda d, ref: d.get("veiculo")),
        ("Autores", lambda d, ref: _nomes_autores(d)),
        ("DOI", lambda d, ref: d.get("doi")),
        ("Link", lambda d, ref: d.get("url")),
        ("Projeto", lambda d, ref: ref["projetos"].get(d.get("projeto_id"), "")),
    ),
}


def _referencias(db) -> dict:
    return {
        "membros": {m["id"]: m["nome"] for m in repo.listar_membros(db)},
        "categorias": {c["id"]: c["titulo"] for c in repo.listar_categorias(db)},
        "projetos": {p["id"]: p["titulo"] for p in repo.listar_projetos(db)},
    }


def resumo_submissao(recurso: str, dados: dict | None, ref: dict) -> list[tuple[str, str]]:
    """Campos legíveis (rótulo, valor) de uma submissão ou do registro atual."""
    if not dados:
        return []
    return [(rotulo, "" if (valor := ler(dados, ref)) is None else str(valor)) for rotulo, ler in _RESUMO[recurso]]


_ENTRADA = {
    "membro": repo.membro_para_entrada,
    "projeto": repo.projeto_para_entrada,
    "publicacao": repo.publicacao_para_entrada,
}


@app.route("/admin/links/<int:link_id>/delete", methods=["POST"])
@login_required
def admin_revogar_link(link_id: int):
    return _salvar("link", pagina_admin_pendentes, url_for("admin_pending") + "#links",
                   lambda: repo.revogar_link(get_db(), link_id), "Link revogado.")


def pagina_admin_pendentes(_rascunhos: dict | None = None):
    db = get_db()
    ref = _referencias(db)  # uma leitura só para todas as submissões da página
    submissoes = []
    for submissao in repo.listar_submissoes(db, "pendente"):
        atual = _ENTRADA[submissao["recurso"]](submissao["atual"]) if submissao["atual"] else None
        submissoes.append(
            {
                **submissao,
                "campos": resumo_submissao(submissao["recurso"], submissao["dados"], ref),
                "campos_atuais": resumo_submissao(submissao["recurso"], atual, ref),
            }
        )
    return render_template(
        "admin/pending.html",
        submissoes=submissoes,
        historico=repo.listar_submissoes(db, None, limite=15),
        links=repo.listar_links(db, apenas_ativos=True),
    )


@app.route("/admin/pending")
@login_required
def admin_pending():
    return pagina_admin_pendentes()


def _rejeitar(submissao_id: int) -> None:
    submissao = repo.rejeitar_submissao(get_db(), submissao_id, usuario_id())
    apagar_imagem(submissao["dados"].get("foto"))


@app.route("/admin/pending/<int:submission_id>/approve", methods=["POST"])
@login_required
def admin_approve_submission(submission_id: int):
    return _salvar("submissao", pagina_admin_pendentes, url_for("admin_pending"),
                   lambda: repo.aprovar_submissao(get_db(), submission_id, usuario_id()),
                   "Submissão aprovada e publicada no site.")


@app.route("/admin/pending/<int:submission_id>/reject", methods=["POST"])
@login_required
def admin_reject_submission(submission_id: int):
    return _salvar("submissao", pagina_admin_pendentes, url_for("admin_pending"),
                   lambda: _rejeitar(submission_id), "Submissão rejeitada.")


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
_ROTULO_RECURSO = {"membro": "Membro da equipe", "projeto": "Projeto", "publicacao": "Publicação"}


def _gravar_submissao(db, recurso: str, link: dict, entrada: dict) -> None:
    """Valida e guarda o envio como pendente. A foto (membro) só é gravada depois
    que os dados passam na validação, e é apagada se a gravação falhar."""
    validado = _VALIDAR[recurso](entrada)
    dados = {campo: validado[campo] for campo in _CAMPOS_SUBMISSAO[recurso]}
    repo.simular_submissao(db, recurso, link["acao"], link["item_id"], dados)

    def registrar(foto):
        if foto:
            dados["foto"] = foto
        repo.registrar_submissao(db, link, dados)

    arquivo = request.files.get("foto") if recurso == "membro" else None
    com_imagem(arquivo, "pending-team", "foto", registrar)


def _avisar_administradores(db, recurso: str, link: dict) -> None:
    enviar_aviso(
        assunto=f"Nova submissão pendente: {_ROTULO_RECURSO[recurso]}",
        corpo=(
            "Uma nova submissão aguarda validação no painel administrativo.\n\n"
            f"Tipo: {_ROTULO_RECURSO[recurso]} ({link['acao']})\n"
            f"Acesse: {url_externa('admin_pending')}"
        ),
        destinatarios=repo.emails_administradores(db),
    )


@app.route("/submit/<recurso>/<token>", methods=["GET", "POST"])
def submit_resource(recurso: str, token: str):
    """Formulário público aberto pelo link de uso único (cadastrar ou editar)."""
    if recurso not in _CAMPOS_SUBMISSAO:
        abort(404)
    db = get_db()
    link = repo.buscar_link_ativo(db, token, recurso)
    if not link:
        return render_template("submit/invalid.html"), 410

    atual = _OBTER[recurso](db, link["item_id"]) if link["acao"] == "editar" else None
    valores, erros = _FORM[recurso](atual), {}
    if request.method == "POST":
        entrada = {campo: request.form.get(campo) for campo in _CAMPOS_SUBMISSAO[recurso]}
        valores = _sem_nulos(entrada)
        try:
            _gravar_submissao(db, recurso, link, entrada)
        except ErroDominio as exc:
            erros = exc.campos or {"_": exc.mensagem}
        else:
            _avisar_administradores(db, recurso, link)
            return render_template("submit/success.html")

    return render_template(
        "submit/formulario.html",
        recurso=recurso,
        foto_atual=atual.get("foto") if atual and recurso == "membro" else None,
        link=link,
        f=valores,
        erros=erros,
        categorias=repo.listar_categorias(db) if recurso == "membro" else [],
        membros=repo.listar_membros(db) if recurso == "projeto" else [],
        projetos=repo.listar_projetos(db) if recurso == "publicacao" else [],
    ), (422 if erros else 200)


def rodar_local() -> None:
    """Servidor de desenvolvimento em http://127.0.0.1:5000 (produção usa gunicorn).
    O depurador do Werkzeug executa código: só liga com FLASK_DEBUG=1 e nunca fora do localhost."""
    app.config["SESSION_COOKIE_SECURE"] = False  # http://localhost não tem HTTPS
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG", "") == "1")


if __name__ == "__main__":
    rodar_local()
