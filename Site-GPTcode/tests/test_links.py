"""Links de uso unico: gerar -> preencher -> validar (aprovar/rejeitar)."""

from urllib.parse import urlparse

from conftest import TOKEN


def _gerar(cliente, recurso, acao, item_id=None):
    dados = {"recurso": recurso, "acao": acao}
    if item_id is not None:
        dados["item_id"] = item_id
    resposta = cliente.post("/api/v1/links", json=dados, headers=TOKEN)
    assert resposta.status_code == 201, resposta.json
    return urlparse(resposta.json["url"]).path, resposta.json


def test_link_de_edicao_de_membro_fluxo_completo(cliente, categoria, professor):
    caminho, link = _gerar(cliente, "membro", "editar", professor["id"])
    assert "token" in link and link["situacao"] == "ativo"

    formulario = cliente.get(caminho)
    assert formulario.status_code == 200
    assert professor["nome"].encode() in formulario.data  # vem preenchido

    # envio invalido: mostra os erros e NAO consome o link
    invalido = cliente.post(caminho, data={"categoria_id": categoria["id"], "nome": "X", "github_url": "gitlab"})
    assert invalido.status_code == 422
    assert "Informe ao menos 3 caracteres".encode() in invalido.data
    assert cliente.get(caminho).status_code == 200

    valido = cliente.post(
        caminho,
        data={
            "categoria_id": categoria["id"],
            "nome": professor["nome"],
            "funcao": "Coordenador do GPTcode",
            "github_url": "dauster",
            "tags": "Educacao, Tecnologia",
        },
    )
    assert valido.status_code == 200
    assert "Enviado com sucesso".encode() in valido.data
    assert cliente.get(caminho).status_code == 410  # uso unico

    pendentes = cliente.get("/api/v1/submissoes", headers=TOKEN).json
    assert len(pendentes) == 1
    submissao = pendentes[0]
    assert submissao["acao"] == "editar" and submissao["atual"]["funcao"] == "Coordenador"

    aprovada = cliente.post(f"/api/v1/submissoes/{submissao['id']}/aprovar", headers=TOKEN)
    assert aprovada.status_code == 200 and aprovada.json["status"] == "aprovada"
    membro = cliente.get(f"/api/v1/membros/{professor['id']}").json
    assert membro["funcao"] == "Coordenador do GPTcode"
    assert membro["github_url"] == "https://github.com/dauster"
    assert membro["tags"] == ["Educacao", "Tecnologia"]

    segunda = cliente.post(f"/api/v1/submissoes/{submissao['id']}/aprovar", headers=TOKEN)
    assert segunda.status_code == 409


def test_link_de_novo_projeto_cria_ao_aprovar(cliente, professor):
    caminho, _ = _gerar(cliente, "projeto", "criar")
    enviado = cliente.post(
        caminho,
        data={
            "titulo": "Realidade Aumentada no Ensino de Informatica",
            "modalidade": "TCC",
            "orientador_id": professor["id"],
            "participantes": "Alice Alves da Gama e Luidy Baldez de Melo",
        },
    )
    assert enviado.status_code == 200
    assert cliente.get("/api/v1/projetos").json == []  # nada publicado antes da aprovacao

    submissao = cliente.get("/api/v1/submissoes", headers=TOKEN).json[0]
    cliente.post(f"/api/v1/submissoes/{submissao['id']}/aprovar", headers=TOKEN)
    projetos = cliente.get("/api/v1/projetos").json
    assert len(projetos) == 1
    assert [p["nome"] for p in projetos[0]["participantes"]] == ["Alice Alves da Gama", "Luidy Baldez de Melo"]


def test_envio_com_titulo_ja_existente_e_barrado_antes_de_consumir_o_link(cliente):
    cliente.post("/api/v1/projetos", json={"titulo": "Projeto Existente", "modalidade": "OUTRO"}, headers=TOKEN)
    caminho, _ = _gerar(cliente, "projeto", "criar")
    resposta = cliente.post(caminho, data={"titulo": "projeto existente", "modalidade": "TCC"})
    assert resposta.status_code == 422
    assert "Ja existe um projeto com este titulo".encode() in resposta.data
    assert cliente.get(caminho).status_code == 200


def test_link_de_publicacao_rejeitado_nao_altera_nada(cliente):
    publicacao = cliente.post(
        "/api/v1/publicacoes", json={"titulo": "Hipermidias em Dispositivos", "ano": 2021, "autores": ["LIMA, Jose"]}, headers=TOKEN
    ).json
    caminho, _ = _gerar(cliente, "publicacao", "editar", publicacao["id"])
    cliente.post(caminho, data={"titulo": "Titulo alterado", "ano": "2022", "tipo": "artigo", "autores": "LIMA, Jose"})

    submissao = cliente.get("/api/v1/submissoes", headers=TOKEN).json[0]
    rejeitada = cliente.post(f"/api/v1/submissoes/{submissao['id']}/rejeitar", headers=TOKEN)
    assert rejeitada.json["status"] == "rejeitada"
    assert cliente.get(f"/api/v1/publicacoes/{publicacao['id']}").json["titulo"] == "Hipermidias em Dispositivos"
    assert cliente.get("/api/v1/submissoes?status=todas", headers=TOKEN).json[0]["status"] == "rejeitada"


def test_token_de_um_recurso_nao_abre_outro(cliente):
    caminho, _ = _gerar(cliente, "projeto", "criar")
    assert cliente.get(caminho.replace("/projeto/", "/membro/")).status_code == 410
    assert cliente.get("/submit/projeto/token-inventado").status_code == 410
    assert cliente.get("/submit/qualquer/abc").status_code == 404


def test_link_invalido(cliente, professor):
    sem_item = cliente.post("/api/v1/links", json={"recurso": "membro", "acao": "editar"}, headers=TOKEN)
    assert sem_item.status_code == 422
    inexistente = cliente.post("/api/v1/links", json={"recurso": "membro", "acao": "editar", "item_id": 999}, headers=TOKEN)
    assert inexistente.status_code == 404
    assert cliente.post("/api/v1/links", json={"recurso": "membro", "acao": "criar"}).status_code == 401


def test_revogar_link_e_remover_item_invalidam_o_link(cliente, professor):
    caminho, link = _gerar(cliente, "projeto", "criar")
    assert cliente.delete(f"/api/v1/links/{link['id']}", headers=TOKEN).status_code == 204
    assert cliente.get(caminho).status_code == 410

    caminho, _ = _gerar(cliente, "membro", "editar", professor["id"])
    cliente.delete(f"/api/v1/membros/{professor['id']}", headers=TOKEN)
    assert cliente.get(caminho).status_code == 410
    assert cliente.get("/api/v1/links?ativos=1", headers=TOKEN).json == []


def test_link_expirado(cliente, conn):
    caminho, link = _gerar(cliente, "projeto", "criar")
    conn.execute("UPDATE link_submissao SET criado_em = '2020-01-01 00:00:00', expira_em = '2020-01-02 00:00:00' WHERE id = ?", (link["id"],))
    conn.commit()
    assert cliente.get(caminho).status_code == 410


def test_links_gerados_pelo_painel(admin, professor):
    resposta = admin.post(
        "/admin/links",
        data={"recurso": "membro", "acao": "editar", "item_id": professor["id"], "voltar": "/admin/team"},
    )
    assert resposta.status_code == 302 and resposta.headers["Location"].endswith("/admin/team")
    pagina = admin.get("/admin/team")
    assert b"/submit/membro/" in pagina.data  # link exibido para copiar

    externo = admin.post("/admin/links", data={"recurso": "membro", "acao": "criar", "voltar": "https://malicioso.com"})
    assert externo.headers["Location"].endswith("/admin/pending")
