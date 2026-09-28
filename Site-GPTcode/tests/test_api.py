"""Testes do CRUD da API REST (/api/v1)."""

from conftest import TOKEN


# ---------------------------------------------------------------------------
# Autenticacao e indice
# ---------------------------------------------------------------------------

def test_indice_lista_recursos(cliente):
    resposta = cliente.get("/api/v1/")
    assert resposta.status_code == 200
    assert "projetos" in resposta.json["recursos"]
    assert resposta.json["autenticado"] is False


def test_escrita_sem_token_retorna_401(cliente):
    resposta = cliente.post("/api/v1/categorias", json={"titulo": "X"})
    assert resposta.status_code == 401
    assert "WWW-Authenticate" in resposta.headers


def test_token_invalido_retorna_401(cliente):
    resposta = cliente.post("/api/v1/categorias", json={"titulo": "X"}, headers={"Authorization": "Bearer errado"})
    assert resposta.status_code == 401
    assert resposta.json["erro"] == "Token da API invalido."


def test_sessao_do_painel_tambem_autentica_a_api(admin):
    assert admin.post("/api/v1/categorias", json={"titulo": "Via sessao"}).status_code == 201


def test_json_malformado_retorna_400(cliente):
    resposta = cliente.post(
        "/api/v1/categorias", data="{invalido", headers={**TOKEN, "Content-Type": "application/json"}
    )
    assert resposta.status_code == 400


def test_rota_inexistente_da_api_responde_json(cliente):
    resposta = cliente.get("/api/v1/nao-existe")
    assert resposta.status_code == 404
    assert "erro" in resposta.json


# ---------------------------------------------------------------------------
# Categorias
# ---------------------------------------------------------------------------

def test_crud_categoria(cliente):
    criada = cliente.post("/api/v1/categorias", json={"titulo": "Alunos de Graduação"}, headers=TOKEN)
    assert criada.status_code == 201
    assert criada.json["slug"] == "alunos-de-graduacao"
    assert criada.headers["Location"].endswith(f"/api/v1/categorias/{criada.json['id']}")

    alterada = cliente.patch(f"/api/v1/categorias/{criada.json['id']}", json={"titulo": "Graduação"}, headers=TOKEN)
    assert alterada.status_code == 200
    assert alterada.json["titulo"] == "Graduação"
    assert alterada.json["slug"] == "alunos-de-graduacao"  # slug estavel

    assert cliente.delete(f"/api/v1/categorias/{criada.json['id']}", headers=TOKEN).status_code == 204
    assert cliente.get(f"/api/v1/categorias/{criada.json['id']}").status_code == 404


def test_categoria_com_titulo_duplicado_retorna_409(cliente, categoria):
    resposta = cliente.post("/api/v1/categorias", json={"titulo": "professores pesquisadores", "slug": "outra"}, headers=TOKEN)
    assert resposta.status_code == 409


def test_categoria_com_membros_nao_pode_ser_removida(cliente, categoria, professor):
    resposta = cliente.delete(f"/api/v1/categorias/{categoria['id']}", headers=TOKEN)
    assert resposta.status_code == 409
    assert "Mova-os" in resposta.json["erro"]


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

def test_criar_membro_normaliza_links_e_tags(cliente, categoria):
    resposta = cliente.post(
        "/api/v1/membros",
        json={
            "categoria_id": categoria["id"],
            "nome": "  Alice Alves da Gama ",
            "github_url": "AliceAlvesG",
            "lattes_url": "1234567890123456",
            "tags": "Python, web, python, Pesquisa",
            "email": "Alice@IFB.edu.br",
        },
        headers=TOKEN,
    )
    assert resposta.status_code == 201, resposta.json
    membro = resposta.json
    assert membro["nome"] == "Alice Alves da Gama"
    assert membro["github_url"] == "https://github.com/AliceAlvesG"
    assert membro["lattes_url"] == "http://lattes.cnpq.br/1234567890123456"
    assert membro["tags"] == ["Python", "web", "Pesquisa"]
    assert membro["email"] == "alice@ifb.edu.br"
    assert membro["funcao"] is None  # ausencia = NULL, nao string vazia


def test_membro_invalido_retorna_422_com_todos_os_campos(cliente, categoria):
    resposta = cliente.post(
        "/api/v1/membros",
        json={"categoria_id": categoria["id"], "nome": "Al", "github_url": "http://gitlab.com/x", "lattes_url": "admin123", "email": "x@"},
        headers=TOKEN,
    )
    assert resposta.status_code == 422
    assert set(resposta.json["campos"]) >= {"nome", "github_url", "lattes_url", "email"}


def test_membro_com_categoria_inexistente_retorna_422(cliente):
    resposta = cliente.post("/api/v1/membros", json={"categoria_id": 999, "nome": "Fulano de Tal"}, headers=TOKEN)
    assert resposta.status_code == 422
    assert "categoria_id" in resposta.json["campos"]


def test_email_de_membro_e_unico(cliente, categoria):
    dados = {"categoria_id": categoria["id"], "nome": "Pessoa Um", "email": "a@b.com"}
    assert cliente.post("/api/v1/membros", json=dados, headers=TOKEN).status_code == 201
    resposta = cliente.post("/api/v1/membros", json={**dados, "nome": "Pessoa Dois", "email": "A@B.com"}, headers=TOKEN)
    assert resposta.status_code == 409
    assert "email" in resposta.json["campos"]


def test_patch_altera_so_os_campos_enviados_e_put_substitui(cliente, categoria):
    criado = cliente.post(
        "/api/v1/membros",
        json={"categoria_id": categoria["id"], "nome": "Mateus Aires", "funcao": "Bolsista", "tags": ["IA"]},
        headers=TOKEN,
    ).json
    patch = cliente.patch(f"/api/v1/membros/{criado['id']}", json={"descricao": "Pesquisa em IA."}, headers=TOKEN).json
    assert patch["funcao"] == "Bolsista" and patch["tags"] == ["IA"] and patch["descricao"] == "Pesquisa em IA."

    put = cliente.put(
        f"/api/v1/membros/{criado['id']}", json={"categoria_id": categoria["id"], "nome": "Mateus Nascimento Aires"}, headers=TOKEN
    ).json
    assert put["funcao"] is None and put["tags"] == [] and put["descricao"] is None


def test_membro_inativo_e_email_ficam_ocultos_para_o_publico(cliente, categoria):
    visivel = cliente.post(
        "/api/v1/membros", json={"categoria_id": categoria["id"], "nome": "Visivel", "email": "v@x.com"}, headers=TOKEN
    ).json
    oculto = cliente.post(
        "/api/v1/membros", json={"categoria_id": categoria["id"], "nome": "Oculto", "ativo": False}, headers=TOKEN
    ).json

    publico = cliente.get("/api/v1/membros").json
    assert [m["id"] for m in publico] == [visivel["id"]]
    assert "email" not in publico[0]
    assert cliente.get(f"/api/v1/membros/{oculto['id']}").status_code == 404

    autenticado = cliente.get("/api/v1/membros", headers=TOKEN).json
    assert len(autenticado) == 2
    assert cliente.get("/api/v1/membros?ativo=false", headers=TOKEN).json[0]["id"] == oculto["id"]


def test_filtrar_membros_por_categoria(cliente, categoria, professor):
    outra = cliente.post("/api/v1/categorias", json={"titulo": "Externos"}, headers=TOKEN).json
    cliente.post("/api/v1/membros", json={"categoria_id": outra["id"], "nome": "Colaborador"}, headers=TOKEN)
    assert [m["nome"] for m in cliente.get("/api/v1/membros?categoria=externos").json] == ["Colaborador"]


def test_remover_membro(cliente, professor):
    assert cliente.delete(f"/api/v1/membros/{professor['id']}", headers=TOKEN).status_code == 204
    assert cliente.get(f"/api/v1/membros/{professor['id']}", headers=TOKEN).status_code == 404


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

def _projeto(cliente, **extra):
    dados = {"titulo": "Game Based Learning para estruturas de dados", "modalidade": "PIBITI", "ano_inicio": 2025, "ano_fim": 2026}
    dados.update(extra)
    return cliente.post("/api/v1/projetos", json=dados, headers=TOKEN)


def test_criar_projeto_vincula_participantes_pelo_nome(cliente, categoria, professor):
    aluna = cliente.post("/api/v1/membros", json={"categoria_id": categoria["id"], "nome": "Mayara Vieira Martins Santos"}, headers=TOKEN).json
    resposta = _projeto(
        cliente,
        orientador_id=professor["id"],
        participantes="mayara vieira martins santos e Luiz Fernando Dobbin\nCarla Souza (coorientador)",
    )
    assert resposta.status_code == 201, resposta.json
    projeto = resposta.json
    assert projeto["rotulo"] == "PIBITI 2025/2026"
    assert projeto["orientador"]["nome"] == professor["nome"]
    assert [(p["nome"], p["membro_id"], p["papel"]) for p in projeto["participantes"]] == [
        ("Mayara Vieira Martins Santos", aluna["id"], "estudante"),
        ("Luiz Fernando Dobbin", None, "estudante"),
        ("Carla Souza", None, "coorientador"),
    ]


def test_modalidade_aceita_rotulo_antigo(cliente):
    assert _projeto(cliente, modalidade="PTCC/TCC", ano_inicio=None, ano_fim=None).json["modalidade"] == "TCC"


def test_regras_de_negocio_do_projeto(cliente):
    fim_antes = _projeto(cliente, ano_inicio=2026, ano_fim=2024)
    assert fim_antes.status_code == 422 and "ano_fim" in fim_antes.json["campos"]

    concluido_sem_fim = _projeto(cliente, status="concluido", ano_fim=None)
    assert concluido_sem_fim.status_code == 422 and "ano_fim" in concluido_sem_fim.json["campos"]

    modalidade = _projeto(cliente, modalidade="Mestrado")
    assert modalidade.status_code == 422 and "modalidade" in modalidade.json["campos"]

    repetido = _projeto(cliente, participantes=["Ana Maria", "ana maria"])
    assert repetido.status_code == 422 and "participantes" in repetido.json["campos"]

    orientador = _projeto(cliente, orientador_id=999)
    assert orientador.status_code == 422 and "orientador_id" in orientador.json["campos"]


def test_titulo_de_projeto_e_unico(cliente):
    assert _projeto(cliente).status_code == 201
    assert _projeto(cliente, titulo="GAME BASED LEARNING PARA ESTRUTURAS DE DADOS").status_code == 409


def test_orientador_nao_pode_ser_removido(cliente, professor):
    _projeto(cliente, orientador_id=professor["id"])
    resposta = cliente.delete(f"/api/v1/membros/{professor['id']}", headers=TOKEN)
    assert resposta.status_code == 409
    assert "orienta 1 projeto" in resposta.json["erro"]


def test_remover_membro_preserva_nome_no_projeto(cliente, categoria):
    aluno = cliente.post("/api/v1/membros", json={"categoria_id": categoria["id"], "nome": "Savio Vinicius"}, headers=TOKEN).json
    projeto = _projeto(cliente, participantes=[{"membro_id": aluno["id"]}]).json
    assert projeto["participantes"][0]["membro_id"] == aluno["id"]

    cliente.delete(f"/api/v1/membros/{aluno['id']}", headers=TOKEN)
    participante = cliente.get(f"/api/v1/projetos/{projeto['id']}").json["participantes"][0]
    assert participante == {**participante, "nome": "Savio Vinicius", "membro_id": None}


def test_filtrar_e_remover_projeto(cliente):
    projeto = _projeto(cliente).json
    _projeto(cliente, titulo="Dashboard de Autoavaliacao", modalidade="TCC")
    assert len(cliente.get("/api/v1/projetos?modalidade=pibiti").json) == 1
    assert cliente.delete(f"/api/v1/projetos/{projeto['id']}", headers=TOKEN).status_code == 204
    assert cliente.get(f"/api/v1/projetos/{projeto['id']}").status_code == 404


# ---------------------------------------------------------------------------
# Publicacoes
# ---------------------------------------------------------------------------

def _publicacao(cliente, **extra):
    dados = {
        "titulo": "Modelo Visual Baseado em Blocos",
        "ano": 2021,
        "veiculo": "Revista Brasileira de Informatica na Educacao",
        "autores": ["PEREIRA, Dauster", "GOMES, Ricardo"],
    }
    dados.update(extra)
    return cliente.post("/api/v1/publicacoes", json=dados, headers=TOKEN)


def test_criar_publicacao_normaliza_doi(cliente):
    resposta = _publicacao(cliente, doi="https://doi.org/10.5753/rbie.2021.001", autores="PEREIRA, Dauster\nGOMES, Ricardo")
    assert resposta.status_code == 201, resposta.json
    publicacao = resposta.json
    assert publicacao["doi"] == "10.5753/rbie.2021.001"
    assert publicacao["link"] == "https://doi.org/10.5753/rbie.2021.001"
    assert [a["nome_citacao"] for a in publicacao["autores"]] == ["PEREIRA, Dauster", "GOMES, Ricardo"]
    assert [a["ordem"] for a in publicacao["autores"]] == [1, 2]


def test_regras_de_negocio_da_publicacao(cliente):
    sem_autor = _publicacao(cliente, autores=[])
    assert sem_autor.status_code == 422 and "autores" in sem_autor.json["campos"]

    ano = _publicacao(cliente, ano=1800)
    assert ano.status_code == 422 and "ano" in ano.json["campos"]

    doi = _publicacao(cliente, doi="nao-e-doi")
    assert doi.status_code == 422 and "doi" in doi.json["campos"]

    url = _publicacao(cliente, url="ftp://arquivo")
    assert url.status_code == 422 and "url" in url.json["campos"]


def test_mesma_publicacao_no_mesmo_ano_e_duplicidade(cliente):
    assert _publicacao(cliente, doi="10.1000/abc").status_code == 201
    assert _publicacao(cliente, titulo="Outro titulo qualquer", doi="10.1000/abc").status_code == 409
    assert _publicacao(cliente, titulo="modelo visual baseado em blocos").status_code == 409
    assert _publicacao(cliente, ano=2022).status_code == 201


def test_filtros_de_publicacoes(cliente):
    _publicacao(cliente)
    _publicacao(cliente, titulo="Robotica Educativa no ensino", ano=2018, tipo="anais")
    assert [p["ano"] for p in cliente.get("/api/v1/publicacoes").json] == [2021, 2018]
    assert len(cliente.get("/api/v1/publicacoes?ano=2018").json) == 1
    assert len(cliente.get("/api/v1/publicacoes?tipo=anais").json) == 1
    assert cliente.get("/api/v1/publicacoes?ano=abc").status_code == 422


def test_remover_projeto_desvincula_publicacao(cliente):
    projeto = _projeto(cliente).json
    publicacao = _publicacao(cliente, projeto_id=projeto["id"]).json
    assert publicacao["projeto"]["id"] == projeto["id"]
    cliente.delete(f"/api/v1/projetos/{projeto['id']}", headers=TOKEN)
    assert cliente.get(f"/api/v1/publicacoes/{publicacao['id']}").json["projeto_id"] is None


# ---------------------------------------------------------------------------
# Contatos, configuracoes, destaque e mensagens
# ---------------------------------------------------------------------------

def test_contato_de_email_gera_link_e_icone(cliente):
    resposta = cliente.post("/api/v1/contatos", json={"tipo": "email", "titulo": "E-mail", "valor": "GPT@ifb.edu.br"}, headers=TOKEN)
    assert resposta.status_code == 201
    assert resposta.json["link"] == "mailto:gpt@ifb.edu.br"
    assert resposta.json["icone"] == "bi-envelope-fill"

    invalido = cliente.post("/api/v1/contatos", json={"tipo": "email", "titulo": "E-mail", "valor": "sem-arroba"}, headers=TOKEN)
    assert invalido.status_code == 422

    duplicado = cliente.post("/api/v1/contatos", json={"tipo": "email", "titulo": "Outro", "valor": "gpt@ifb.edu.br"}, headers=TOKEN)
    assert duplicado.status_code == 409


def test_crud_contato(cliente):
    contato = cliente.post(
        "/api/v1/contatos", json={"tipo": "endereco", "titulo": "Localizacao", "valor": "SGAN 610"}, headers=TOKEN
    ).json
    alterado = cliente.patch(f"/api/v1/contatos/{contato['id']}", json={"subtitulo": "CEP 70830-450"}, headers=TOKEN).json
    assert alterado["valor"] == "SGAN 610" and alterado["subtitulo"] == "CEP 70830-450"
    assert cliente.delete(f"/api/v1/contatos/{contato['id']}", headers=TOKEN).status_code == 204


def test_configuracoes(cliente):
    resposta = cliente.patch("/api/v1/configuracoes", json={"hero_title": "GPTcode"}, headers=TOKEN)
    assert resposta.status_code == 200 and resposta.json["hero_title"] == "GPTcode"
    assert cliente.patch("/api/v1/configuracoes", json={"chave_inventada": "x"}, headers=TOKEN).status_code == 422
    link_ruim = cliente.patch("/api/v1/configuracoes", json={"about_primary_button_link": "javascript:alert(1)"}, headers=TOKEN)
    assert link_ruim.status_code == 422


def test_destaque_e_limpo_quando_o_item_e_removido(cliente):
    projeto = _projeto(cliente).json
    resposta = cliente.put("/api/v1/destaque", json={"tipo": "projeto", "item_id": projeto["id"]}, headers=TOKEN)
    assert resposta.json["tipo"] == "projeto"
    cliente.delete(f"/api/v1/projetos/{projeto['id']}", headers=TOKEN)
    assert cliente.get("/api/v1/destaque").json["tipo"] == "nenhum"
    assert cliente.put("/api/v1/destaque", json={"tipo": "publicacao", "item_id": 999}, headers=TOKEN).status_code == 422


def test_mensagens_de_contato(cliente):
    enviada = cliente.post(
        "/api/v1/mensagens",
        json={"nome_remetente": "Visitante", "email_remetente": "v@exemplo.com", "mensagem": "Quero participar do grupo."},
    )
    assert enviada.status_code == 201
    assert set(enviada.json) == {"id", "recebida_em"}  # publico nao recebe os dados de volta

    curta = cliente.post("/api/v1/mensagens", json={"nome_remetente": "V", "email_remetente": "x", "mensagem": "oi"})
    assert curta.status_code == 422 and set(curta.json["campos"]) == {"nome_remetente", "email_remetente", "mensagem"}

    assert cliente.get("/api/v1/mensagens").status_code == 401
    assert len(cliente.get("/api/v1/mensagens?nao_lidas=1", headers=TOKEN).json) == 1
    lida = cliente.patch(f"/api/v1/mensagens/{enviada.json['id']}", json={"lida": True}, headers=TOKEN)
    assert lida.json["lida"] is True
    assert cliente.get("/api/v1/mensagens?nao_lidas=1", headers=TOKEN).json == []
    assert cliente.delete(f"/api/v1/mensagens/{enviada.json['id']}", headers=TOKEN).status_code == 204


def test_estatisticas_exigem_autenticacao(cliente):
    assert cliente.get("/api/v1/estatisticas").status_code == 401
    assert cliente.get("/api/v1/estatisticas", headers=TOKEN).json["projetos"] == 0
