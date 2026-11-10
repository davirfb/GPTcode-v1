"""API REST do site GPTcode (prefixo /api/v1).

Convencoes:
  * leitura (GET) do conteudo publico e aberta; escrita exige autenticacao
    (ver backend.auth.api_auth_required);
  * corpo das requisicoes em JSON; rotas com imagem aceitam multipart/form-data;
  * PUT substitui o registro inteiro, PATCH altera so os campos enviados;
  * respostas: 200 OK, 201 Created (+ Location), 204 No Content,
    400 JSON malformado, 401 sem autenticacao, 404 inexistente,
    409 conflito (duplicidade / registro em uso), 422 regra de negocio violada.
Documentacao completa: docs/API.md
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, url_for
from werkzeug.exceptions import BadRequest

from backend import repositorio as repo
from backend.auth import api_auth_required, api_somente_admin_required
from backend.contexto import esta_autenticado, get_db, url_do_link, usuario_id
from backend.erros import ErroDominio, NaoEncontrado, ValidacaoErro
from backend.uploads import apagar_imagem, com_imagem
from backend.validadores import converter_booleano, converter_inteiro

api = Blueprint("api", __name__, url_prefix="/api/v1")


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

@api.errorhandler(ErroDominio)
def _erro_dominio(exc: ErroDominio):
    return jsonify(exc.como_dict()), exc.status_http


def dados_requisicao() -> dict:
    """Corpo da requisicao como dict (JSON ou formulario)."""
    if request.is_json:
        try:
            corpo = request.get_json()
        except BadRequest:
            raise ErroDominio("JSON malformado.")
        if not isinstance(corpo, dict):
            raise ErroDominio("O corpo da requisição deve ser um objeto JSON.")
        return corpo
    dados = {}
    for chave in request.form:
        valores = request.form.getlist(chave)
        dados[chave] = valores if len(valores) > 1 else valores[0]
    return dados


def criado(corpo: dict, endpoint: str, **valores):
    resposta = jsonify(corpo)
    resposta.status_code = 201
    resposta.headers["Location"] = url_for(endpoint, **valores)
    return resposta


def sem_conteudo():
    return "", 204


def _inteiro_arg(nome: str) -> int | None:
    valor = request.args.get(nome)
    if valor in (None, ""):
        return None
    numero = converter_inteiro(valor)
    if numero is None:
        raise ValidacaoErro({nome: "Informe um número inteiro."})
    return numero


def _bool_arg(nome: str) -> bool | None:
    """Filtro opcional verdadeiro/falso; valor não reconhecido é erro 422 (antes era ignorado)."""
    valor = request.args.get(nome)
    if valor in (None, ""):
        return None
    convertido = converter_booleano(valor)
    if convertido is None:
        raise ValidacaoErro({nome: "Use true ou false."})
    return convertido


def _membro_publico(membro: dict) -> dict:
    if esta_autenticado():
        return membro
    return {chave: valor for chave, valor in membro.items() if chave != "email"}


# ---------------------------------------------------------------------------
# Indice
# ---------------------------------------------------------------------------

@api.get("/")
def indice():
    return jsonify(
        {
            "nome": "API do site GPTcode",
            "versao": "1",
            "autenticado": esta_autenticado(),
            "recursos": {
                "categorias": url_for("api.listar_categorias"),
                "membros": url_for("api.listar_membros"),
                "tags": url_for("api.listar_tags"),
                "projetos": url_for("api.listar_projetos"),
                "publicacoes": url_for("api.listar_publicacoes"),
                "contatos": url_for("api.listar_contatos"),
                "parceiros": url_for("api.listar_parceiros"),
                "slider": url_for("api.listar_slider"),
                "configuracoes": url_for("api.obter_configuracoes"),
                "destaque": url_for("api.obter_destaque"),
                "mensagens": url_for("api.listar_mensagens"),
                "links": url_for("api.listar_links"),
                "submissoes": url_for("api.listar_submissoes"),
                "estatisticas": url_for("api.estatisticas"),
            },
            "documentacao": "docs/API.md",
        }
    )


@api.get("/estatisticas")
@api_auth_required
def estatisticas():
    return jsonify(repo.estatisticas(get_db()))


@api.get("/usuarios")
@api_somente_admin_required
def listar_usuarios():
    return jsonify(repo.listar_usuarios(get_db()))


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

@api.get("/categorias")
def listar_categorias():
    return jsonify(repo.listar_categorias(get_db()))


@api.get("/categorias/<int:item_id>")
def obter_categoria(item_id: int):
    return jsonify(repo.obter_categoria(get_db(), item_id))


@api.post("/categorias")
@api_auth_required
def criar_categoria():
    categoria = repo.criar_categoria(get_db(), dados_requisicao())
    return criado(categoria, "api.obter_categoria", item_id=categoria["id"])


@api.route("/categorias/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_categoria(item_id: int):
    parcial = request.method == "PATCH"
    return jsonify(repo.atualizar_categoria(get_db(), item_id, dados_requisicao(), parcial=parcial))


@api.delete("/categorias/<int:item_id>")
@api_auth_required
def remover_categoria(item_id: int):
    repo.remover_categoria(get_db(), item_id)
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

@api.get("/membros")
def listar_membros():
    ativo = _bool_arg("ativo")
    apenas_ativos = True if not esta_autenticado() else ativo is True
    membros = repo.listar_membros(get_db(), categoria=request.args.get("categoria"), apenas_ativos=apenas_ativos)
    if esta_autenticado() and ativo is False:
        membros = [m for m in membros if not m["ativo"]]
    return jsonify([_membro_publico(m) for m in membros])


@api.get("/membros/<int:item_id>")
def obter_membro(item_id: int):
    membro = repo.obter_membro(get_db(), item_id)
    if not membro["ativo"] and not esta_autenticado():
        raise NaoEncontrado("Membro não encontrado.")
    return jsonify(_membro_publico(membro))


@api.post("/membros")
@api_auth_required
def criar_membro():
    dados = dados_requisicao()
    membro = com_imagem(request.files.get("foto"), "team", "foto",
                        lambda foto: repo.criar_membro(get_db(), dados, usuario_id(), foto=foto))
    return criado(membro, "api.obter_membro", item_id=membro["id"])


@api.route("/membros/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_membro(item_id: int):
    parcial = request.method == "PATCH"
    return jsonify(repo.atualizar_membro(get_db(), item_id, dados_requisicao(), usuario_id(), parcial=parcial))


@api.put("/membros/<int:item_id>/foto")
@api_auth_required
def definir_foto_membro(item_id: int):
    repo.obter_membro(get_db(), item_id)
    com_imagem(request.files.get("foto"), "team", "foto",
               lambda foto: repo.definir_foto_membro(get_db(), item_id, foto, usuario_id()),
               obrigatoria=True, mensagem_obrigatoria="Envie o arquivo no campo 'foto' (multipart/form-data).")
    return jsonify(repo.obter_membro(get_db(), item_id))


@api.delete("/membros/<int:item_id>")
@api_auth_required
def remover_membro(item_id: int):
    membro = repo.remover_membro(get_db(), item_id)
    apagar_imagem(membro["foto"])
    return sem_conteudo()


@api.get("/tags")
def listar_tags():
    return jsonify(repo.listar_tags(get_db()))


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

@api.get("/projetos")
def listar_projetos():
    return jsonify(
        repo.listar_projetos(get_db(), status=request.args.get("status"), modalidade=request.args.get("modalidade"))
    )


@api.get("/projetos/<int:item_id>")
def obter_projeto(item_id: int):
    return jsonify(repo.obter_projeto(get_db(), item_id))


@api.post("/projetos")
@api_auth_required
def criar_projeto():
    projeto = repo.criar_projeto(get_db(), dados_requisicao(), usuario_id())
    return criado(projeto, "api.obter_projeto", item_id=projeto["id"])


@api.route("/projetos/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_projeto(item_id: int):
    parcial = request.method == "PATCH"
    return jsonify(repo.atualizar_projeto(get_db(), item_id, dados_requisicao(), usuario_id(), parcial=parcial))


@api.delete("/projetos/<int:item_id>")
@api_auth_required
def remover_projeto(item_id: int):
    repo.remover_projeto(get_db(), item_id)
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Publicacoes
# ---------------------------------------------------------------------------

@api.get("/publicacoes")
def listar_publicacoes():
    return jsonify(
        repo.listar_publicacoes(
            get_db(),
            ano=_inteiro_arg("ano"),
            tipo=request.args.get("tipo"),
            projeto_id=_inteiro_arg("projeto_id"),
        )
    )


@api.get("/publicacoes/<int:item_id>")
def obter_publicacao(item_id: int):
    return jsonify(repo.obter_publicacao(get_db(), item_id))


@api.post("/publicacoes")
@api_auth_required
def criar_publicacao():
    publicacao = repo.criar_publicacao(get_db(), dados_requisicao(), usuario_id())
    return criado(publicacao, "api.obter_publicacao", item_id=publicacao["id"])


@api.route("/publicacoes/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_publicacao(item_id: int):
    parcial = request.method == "PATCH"
    return jsonify(repo.atualizar_publicacao(get_db(), item_id, dados_requisicao(), usuario_id(), parcial=parcial))


@api.delete("/publicacoes/<int:item_id>")
@api_auth_required
def remover_publicacao(item_id: int):
    repo.remover_publicacao(get_db(), item_id)
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Contatos
# ---------------------------------------------------------------------------

@api.get("/contatos")
def listar_contatos():
    return jsonify(repo.listar_contatos(get_db()))


@api.get("/contatos/<int:item_id>")
def obter_contato(item_id: int):
    return jsonify(repo.obter_contato(get_db(), item_id))


@api.post("/contatos")
@api_auth_required
def criar_contato():
    contato = repo.criar_contato(get_db(), dados_requisicao(), usuario_id())
    return criado(contato, "api.obter_contato", item_id=contato["id"])


@api.route("/contatos/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_contato(item_id: int):
    parcial = request.method == "PATCH"
    return jsonify(repo.atualizar_contato(get_db(), item_id, dados_requisicao(), usuario_id(), parcial=parcial))


@api.delete("/contatos/<int:item_id>")
@api_auth_required
def remover_contato(item_id: int):
    repo.remover_contato(get_db(), item_id)
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Parceiros e slider (com imagem)
# ---------------------------------------------------------------------------

@api.get("/parceiros")
def listar_parceiros():
    return jsonify(repo.listar_parceiros(get_db()))


@api.get("/parceiros/<int:item_id>")
def obter_parceiro(item_id: int):
    return jsonify(repo.obter_parceiro(get_db(), item_id))


@api.post("/parceiros")
@api_auth_required
def criar_parceiro():
    dados = dados_requisicao()
    parceiro = com_imagem(request.files.get("logo"), "partners", "logo",
                          lambda logo: repo.criar_parceiro(get_db(), dados, logo), obrigatoria=True,
                          mensagem_obrigatoria="Envie o logotipo no campo 'logo' (multipart/form-data).")
    return criado(parceiro, "api.obter_parceiro", item_id=parceiro["id"])


@api.route("/parceiros/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_parceiro(item_id: int):
    dados = dados_requisicao()
    parceiro, _antiga = com_imagem(
        request.files.get("logo"), "partners", "logo",
        lambda logo: repo.atualizar_parceiro(get_db(), item_id, dados, logo, parcial=request.method == "PATCH"))
    return jsonify(parceiro)


@api.delete("/parceiros/<int:item_id>")
@api_auth_required
def remover_parceiro(item_id: int):
    apagar_imagem(repo.remover_parceiro(get_db(), item_id)["logo"])
    return sem_conteudo()


@api.get("/slider")
def listar_slider():
    return jsonify(repo.listar_slider(get_db()))


@api.get("/slider/<int:item_id>")
def obter_slider(item_id: int):
    return jsonify(repo.obter_slider(get_db(), item_id))


@api.post("/slider")
@api_auth_required
def criar_slider():
    dados = dados_requisicao()
    slide = com_imagem(request.files.get("imagem"), "about-slider", "imagem",
                       lambda imagem: repo.criar_slider(get_db(), dados, imagem), obrigatoria=True,
                       mensagem_obrigatoria="Envie a imagem no campo 'imagem' (multipart/form-data).")
    return criado(slide, "api.obter_slider", item_id=slide["id"])


@api.route("/slider/<int:item_id>", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_slider(item_id: int):
    dados = dados_requisicao()
    slide, _antiga = com_imagem(
        request.files.get("imagem"), "about-slider", "imagem",
        lambda imagem: repo.atualizar_slider(get_db(), item_id, dados, imagem, parcial=request.method == "PATCH"))
    return jsonify(slide)


@api.delete("/slider/<int:item_id>")
@api_auth_required
def remover_slider(item_id: int):
    apagar_imagem(repo.remover_slider(get_db(), item_id)["imagem"])
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Configuracoes e destaque
# ---------------------------------------------------------------------------

@api.get("/configuracoes")
def obter_configuracoes():
    return jsonify(repo.obter_configuracoes(get_db()))


@api.route("/configuracoes", methods=["PUT", "PATCH"])
@api_auth_required
def atualizar_configuracoes():
    return jsonify(repo.atualizar_configuracoes(get_db(), dados_requisicao(), usuario_id()))


@api.get("/destaque")
def obter_destaque():
    return jsonify(repo.obter_destaque(get_db()))


@api.put("/destaque")
@api_auth_required
def definir_destaque():
    return jsonify(repo.definir_destaque(get_db(), dados_requisicao()))


# ---------------------------------------------------------------------------
# Mensagens do formulario de contato
# ---------------------------------------------------------------------------

@api.post("/mensagens")
def criar_mensagem():
    """Rota publica: equivale ao envio do formulario da pagina Contato.

    Sem login, so aceita JSON: um formulario HTML de outro site nao consegue
    enviar JSON sem a permissao do navegador (CORS), entao nao da para usar
    os visitantes de terceiros para mandar spam."""
    if not esta_autenticado() and not request.is_json:
        raise ErroDominio("Envie a mensagem em JSON (Content-Type: application/json).")
    mensagem = repo.criar_mensagem(get_db(), dados_requisicao(), ip=request.remote_addr)
    corpo = {"id": mensagem["id"], "recebida_em": mensagem["recebida_em"]}
    if esta_autenticado():
        corpo = mensagem
    resposta = jsonify(corpo)
    resposta.status_code = 201
    return resposta


@api.get("/mensagens")
@api_auth_required
def listar_mensagens():
    return jsonify(repo.listar_mensagens(get_db(), apenas_nao_lidas=_bool_arg("nao_lidas") is True))


@api.get("/mensagens/<int:item_id>")
@api_auth_required
def obter_mensagem(item_id: int):
    return jsonify(repo.obter_mensagem(get_db(), item_id))


@api.patch("/mensagens/<int:item_id>")
@api_auth_required
def marcar_mensagem(item_id: int):
    dados = dados_requisicao()
    lida = converter_booleano(dados.get("lida"))
    if lida is None:
        raise ValidacaoErro({"lida": "Informe true ou false."})
    return jsonify(repo.marcar_mensagem(get_db(), item_id, lida))


@api.delete("/mensagens/<int:item_id>")
@api_auth_required
def remover_mensagem(item_id: int):
    repo.remover_mensagem(get_db(), item_id)
    return sem_conteudo()


# ---------------------------------------------------------------------------
# Links de uso unico e submissoes
# ---------------------------------------------------------------------------

@api.get("/links")
@api_auth_required
def listar_links():
    return jsonify(repo.listar_links(get_db(), apenas_ativos=_bool_arg("ativos") is True))


@api.post("/links")
@api_auth_required
def gerar_link():
    link = repo.gerar_link(get_db(), dados_requisicao(), usuario_id())
    link["url"] = url_do_link(link)
    resposta = jsonify(link)
    resposta.status_code = 201
    return resposta


@api.delete("/links/<int:item_id>")
@api_auth_required
def revogar_link(item_id: int):
    repo.revogar_link(get_db(), item_id)
    return sem_conteudo()


@api.get("/submissoes")
@api_auth_required
def listar_submissoes():
    status = request.args.get("status", "pendente")
    if status not in ("pendente", "aprovada", "rejeitada", "todas"):
        raise ValidacaoErro({"status": "Use pendente, aprovada, rejeitada ou todas."})
    return jsonify(repo.listar_submissoes(get_db(), None if status == "todas" else status))


@api.get("/submissoes/<int:item_id>")
@api_auth_required
def obter_submissao(item_id: int):
    return jsonify(repo.obter_submissao(get_db(), item_id))


@api.post("/submissoes/<int:item_id>/aprovar")
@api_auth_required
def aprovar_submissao(item_id: int):
    return jsonify(repo.aprovar_submissao(get_db(), item_id, usuario_id()))


@api.post("/submissoes/<int:item_id>/rejeitar")
@api_auth_required
def rejeitar_submissao(item_id: int):
    submissao = repo.rejeitar_submissao(get_db(), item_id, usuario_id())
    apagar_imagem(submissao["dados"].get("foto"))
    return jsonify(submissao)
