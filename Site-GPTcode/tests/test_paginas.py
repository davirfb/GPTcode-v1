"""Paginas publicas e formularios do painel administrativo."""

import io

import pytest

from conftest import TOKEN


@pytest.mark.parametrize("url", ["/", "/projetos", "/publicacoes", "/equipe", "/contato", "/admin/login"])
def test_paginas_publicas(cliente, url):
    assert cliente.get(url).status_code == 200


@pytest.mark.parametrize(
    "url",
    ["/admin", "/admin/home", "/admin/projects", "/admin/publications", "/admin/team", "/admin/contato", "/admin/mensagens", "/admin/pending"],
)
def test_painel_exige_login_e_renderiza(cliente, admin, url):
    assert admin.get(url).status_code == 200


def test_painel_sem_login_redireciona(cliente):
    resposta = cliente.get("/admin/projects")
    assert resposta.status_code == 302 and "/admin/login" in resposta.headers["Location"]


def test_formulario_de_contato_publico(cliente):
    invalido = cliente.post("/contato", data={"nome": "Ana", "email": "ana", "mensagem": "oi"})
    assert invalido.status_code == 422
    assert b'value="Ana"' in invalido.data  # o que foi digitado e mantido

    valido = cliente.post("/contato", data={"nome": "Ana", "email": "ana@x.com", "mensagem": "Gostaria de participar."})
    assert valido.status_code == 302
    assert len(cliente.get("/api/v1/mensagens", headers=TOKEN).json) == 1


def test_painel_cria_edita_e_remove_projeto(admin, professor):
    criado = admin.post(
        "/admin/projects/add",
        data={"titulo": "Sistema Web para Avaliacao", "modalidade": "PIBIC", "ano_inicio": "2025", "ano_fim": "2026",
              "orientador_id": str(professor["id"]), "participantes": "Davi Rocha Fortes Bezerra"},
    )
    assert criado.status_code == 302
    projeto = admin.get("/api/v1/projetos").json[0]
    assert projeto["rotulo"] == "PIBIC 2025/2026"

    pagina = admin.get("/projetos")
    assert b"PIBIC 2025/2026" in pagina.data and b"Davi Rocha Fortes Bezerra" in pagina.data

    editado = admin.post(
        f"/admin/projects/{projeto['id']}/update",
        data={"titulo": "Sistema Web para Avaliacao", "modalidade": "PIBIC", "status": "concluido",
              "ano_inicio": "2025", "ano_fim": "2026", "orientador_id": str(professor["id"]), "participantes": ""},
    )
    assert editado.status_code == 302
    assert admin.get(f"/api/v1/projetos/{projeto['id']}").json["status"] == "concluido"

    assert admin.post(f"/admin/projects/{projeto['id']}/delete").status_code == 302
    assert admin.get("/api/v1/projetos").json == []


def test_painel_mostra_erro_e_mantem_o_que_foi_digitado(admin):
    resposta = admin.post(
        "/admin/projects/add",
        data={"titulo": "Projeto com anos trocados", "modalidade": "TCC", "ano_inicio": "2026", "ano_fim": "2020"},
    )
    assert resposta.status_code == 422
    assert "ano_fim: O ano de termino nao pode ser anterior".encode() in resposta.data
    assert b'value="Projeto com anos trocados"' in resposta.data


def test_painel_membro_com_foto_e_checkbox_ativo(admin, categoria):
    resposta = admin.post(
        "/admin/team/members/add",
        data={"categoria_id": str(categoria["id"]), "nome": "Nova Integrante", "tags": "IA",
              "foto": (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "foto.png")},
        content_type="multipart/form-data",
    )
    assert resposta.status_code == 302
    membro = admin.get("/api/v1/membros").json[0]
    assert membro["foto"].startswith("uploads/team/") and membro["ativo"] is False  # checkbox desmarcado

    ruim = admin.post(
        "/admin/team/members/add",
        data={"categoria_id": str(categoria["id"]), "nome": "Outra Pessoa", "foto": (io.BytesIO(b"x"), "virus.exe")},
        content_type="multipart/form-data",
    )
    assert ruim.status_code == 422

    admin.post(f"/admin/team/members/{membro['id']}/delete")
    assert admin.get("/api/v1/membros").json == []


def test_painel_aprova_submissao(admin, professor):
    link = admin.post("/api/v1/links", json={"recurso": "membro", "acao": "editar", "item_id": professor["id"]}).json
    caminho = link["url"].split("localhost", 1)[1]
    admin.post(caminho, data={"categoria_id": professor["categoria_id"], "nome": professor["nome"], "funcao": "Coordenador geral"})

    pendentes = admin.get("/admin/pending")
    assert b"Coordenador geral" in pendentes.data and b"table-warning" in pendentes.data
    submissao = admin.get("/api/v1/submissoes").json[0]

    assert admin.post(f"/admin/pending/{submissao['id']}/approve").status_code == 302
    assert admin.get(f"/api/v1/membros/{professor['id']}").json["funcao"] == "Coordenador geral"
