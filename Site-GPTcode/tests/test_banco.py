"""Restricoes declaradas no schema (ultima barreira, independente da aplicacao)
e migracao do banco antigo (v1)."""

import shutil
import sqlite3
from pathlib import Path

import pytest

from backend import repositorio as repo
from backend.database import connect, init_db

FIXTURE_V1 = Path(__file__).parent / "fixtures" / "gptcode_v1.db"


def _base(conn):
    conn.execute("INSERT INTO categoria_membro (slug, titulo) VALUES ('prof', 'Professores')")
    conn.execute("INSERT INTO membro (categoria_id, nome) VALUES (1, 'Fulano de Tal')")
    conn.execute("INSERT INTO projeto (titulo, modalidade) VALUES ('Projeto Teste', 'TCC')")
    conn.commit()


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO projeto (titulo, modalidade) VALUES ('Outro projeto', 'MESTRADO')",
        "INSERT INTO projeto (titulo, modalidade, ano_inicio, ano_fim) VALUES ('Outro projeto', 'TCC', 2025, 2024)",
        "INSERT INTO projeto (titulo, modalidade, status) VALUES ('Outro projeto', 'TCC', 'concluido')",
        "INSERT INTO publicacao (titulo, ano) VALUES ('Publicacao antiga', 1800)",
        "INSERT INTO publicacao (titulo, ano, doi) VALUES ('Publicacao doi', 2020, 'abc')",
        "INSERT INTO membro (categoria_id, nome, github_url) VALUES (1, 'Beltrano', 'http://gitlab.com/x')",
        "INSERT INTO membro (categoria_id, nome, email) VALUES (1, 'Beltrano', 'sem-arroba')",
        "INSERT INTO membro (categoria_id, nome, ativo) VALUES (1, 'Beltrano', 2)",
        "INSERT INTO projeto_participante (projeto_id) VALUES (1)",
        "INSERT INTO projeto_participante (projeto_id, membro_id, nome_externo) VALUES (1, 1, 'Duplo')",
        "INSERT INTO contato (tipo, titulo, valor) VALUES ('fax', 'Fax', '123')",
        "INSERT INTO contato (tipo, titulo, valor) VALUES ('email', 'E-mail', 'nao-e-email')",
        "INSERT INTO destaque (id) VALUES (2)",
        "UPDATE destaque SET projeto_id = 1, publicacao_id = 1 WHERE id = 1",
        "INSERT INTO link_submissao (token_hash, recurso, acao, expira_em) "
        "VALUES ('" + "a" * 64 + "', 'membro', 'editar', '2099-01-01')",
        "INSERT INTO link_submissao (token_hash, recurso, acao, projeto_id, expira_em) "
        "VALUES ('" + "b" * 64 + "', 'membro', 'editar', 1, '2099-01-01')",
        "INSERT INTO membro (categoria_id, nome) VALUES (99, 'Sem categoria')",
    ],
)
def test_restricoes_do_schema(conn, sql):
    _base(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)


def test_chaves_estrangeiras_estao_ativas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_categoria_com_membro_nao_e_apagada_pelo_banco(conn):
    _base(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM categoria_membro WHERE id = 1")


def test_submissao_so_uma_por_link(conn):
    _base(conn)
    conn.execute(
        "INSERT INTO link_submissao (token_hash, recurso, acao, expira_em) VALUES (?, 'projeto', 'criar', '2099-01-01')",
        ("c" * 64,),
    )
    conn.execute("INSERT INTO submissao (link_id, dados) VALUES (1, '{}')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO submissao (link_id, dados) VALUES (1, '{}')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE submissao SET dados = 'nao e json'")


def test_tag_orfa_e_removida(conn):
    _base(conn)
    categoria_id = conn.execute("SELECT id FROM categoria_membro").fetchone()[0]
    membro = repo.criar_membro(conn, {"categoria_id": categoria_id, "nome": "Com Tags", "tags": "IA, Web"})
    repo.atualizar_membro(conn, membro["id"], {"tags": "Web"}, parcial=True)
    assert [t["nome"] for t in repo.listar_tags(conn)] == ["Web"]


def test_atualizado_em_e_mantido_pelo_gatilho(conn):
    _base(conn)
    conn.execute("UPDATE projeto SET atualizado_em = '2000-01-01 00:00:00'")
    conn.commit()
    conn.execute("UPDATE projeto SET descricao = 'nova' WHERE id = 1")
    conn.commit()
    assert conn.execute("SELECT atualizado_em FROM projeto").fetchone()[0] > "2000-01-01 00:00:00"


def test_migracao_do_banco_v1(tmp_path):
    caminho = tmp_path / "gptcode.db"
    shutil.copy(FIXTURE_V1, caminho)

    avisos = init_db(caminho)

    assert (tmp_path / "gptcode.db.v1.bak").exists()
    assert any("admin123" in aviso for aviso in avisos)
    conn = connect(caminho)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        estatisticas = repo.estatisticas(conn)
        assert (estatisticas["membros"], estatisticas["projetos"], estatisticas["publicacoes"]) == (20, 9, 10)

        projetos = repo.listar_projetos(conn)
        assert projetos[0]["rotulo"] == "PIBIC 2025/2026"
        assert all(p["orientador"] for p in projetos)
        dupla = next(p for p in projetos if p["titulo"].startswith("Dashboard"))
        assert [x["nome"] for x in dupla["participantes"]] == ["Davi Campos Parente", "Ivanilson Paixao Cirqueira"]
        assert all(x["membro_id"] for x in dupla["participantes"])

        davi = next(m for m in repo.listar_membros(conn) if m["nome"] == "Davi Rocha Fortes Bezerra")
        assert davi["lattes_url"] is None  # 'admin123' descartado

        contatos = {c["tipo"] for c in repo.listar_contatos(conn)}
        assert contatos == {"endereco", "email"}
    finally:
        conn.close()

    assert init_db(caminho) == []  # idempotente


def test_instalacao_nova_usa_o_conteudo_do_json(tmp_path):
    caminho = tmp_path / "novo.db"
    init_db(caminho)
    conn = connect(caminho)
    try:
        assert repo.estatisticas(conn)["membros"] > 0
    finally:
        conn.close()
