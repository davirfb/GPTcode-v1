"""Camada de acesso a dados (CRUD) sobre o SQLite.

Cada operacao de escrita:
  1. valida a entrada com `backend.validadores` (regras de negocio);
  2. confere a existencia das chaves estrangeiras (erro 422 amigavel);
  3. grava dentro de uma transacao; violacoes de integridade do banco
     sao traduzidas para `Conflito`/`ValidacaoErro` (ver backend.erros).

Operacoes de escrita publicas retornam o registro ja serializado, no
mesmo formato usado pela API e pelos templates.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import secrets
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from backend import validadores as v
from backend.erros import (
    Conflito,
    LimiteExcedido,
    NaoEncontrado,
    ValidacaoErro,
    traduzir_integridade,
)


# ---------------------------------------------------------------------------
# Infraestrutura
# ---------------------------------------------------------------------------

@contextmanager
def transacao(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        with conn:
            yield conn
    except sqlite3.IntegrityError as exc:
        raise traduzir_integridade(exc) from exc


def agora_sql(dias: int = 0) -> str:
    momento = datetime.now(timezone.utc) + timedelta(days=dias)
    return momento.strftime("%Y-%m-%d %H:%M:%S")


def _existe(conn, tabela: str, item_id: int | None) -> bool:
    if item_id is None:
        return False
    return conn.execute(f"SELECT 1 FROM {tabela} WHERE id = ?", (item_id,)).fetchone() is not None


def _proxima_ordem(conn, tabela: str, filtro: str = "", params: tuple = ()) -> int:
    where = f"WHERE {filtro}" if filtro else ""
    linha = conn.execute(
        f"SELECT COALESCE(MAX(ordem_exibicao) + 1, 0) FROM {tabela} {where}", params
    ).fetchone()
    return linha[0]


def _mesclar(atual: dict, alteracoes: dict) -> dict:
    """PATCH: campos enviados substituem os atuais; o resto e mantido."""
    return {**atual, **alteracoes}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Limite de tentativas (força bruta no login e spam no contato)
# ---------------------------------------------------------------------------

def _momento(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def _minutos_ate(texto: str) -> int:
    segundos = (_momento(texto) - datetime.now(timezone.utc)).total_seconds()
    return max(1, -(-int(segundos) // 60))  # arredonda para cima: 15 min mostram "15", não "16"


def minutos_bloqueado(conn, chave: str) -> int:
    """Minutos que faltam para a chave voltar a ser aceita (0 = liberada)."""
    linha = conn.execute("SELECT bloqueado_ate FROM limite_acesso WHERE chave = ?", (chave,)).fetchone()
    if linha and linha["bloqueado_ate"] and linha["bloqueado_ate"] > agora_sql():
        return _minutos_ate(linha["bloqueado_ate"])
    return 0


def rede_do_ip(ip: str | None) -> str:
    """Agrupa o IP para o limite: IPv6 por /64 (quem tem uma faixa /64 tem 2^64 endereços
    para trocar), IPv4-mapeado como IPv4."""
    try:
        endereco = ipaddress.ip_address(ip or "")
    except ValueError:
        return ip or "desconhecido"
    if endereco.version == 6 and endereco.ipv4_mapped:
        return str(endereco.ipv4_mapped)
    if endereco.version == 6:
        return str(ipaddress.ip_network(f"{endereco}/64", strict=False))
    return str(endereco)


def reservar_tentativa(conn, chave: str, maximo: int, minutos_janela: int, minutos_bloqueio: int,
                       email: str | None = None) -> int:
    """Conta UMA tentativa na janela atual, de forma atômica (lock de escrita do SQLite),
    e devolve o total. Ao chegar em `maximo` a chave fica bloqueada. Quem recebe um total
    acima de `maximo` perdeu a corrida e deve ser recusado sem gastar CPU."""
    agora = agora_sql()
    inicio_janela = (datetime.now(timezone.utc) - timedelta(minutes=minutos_janela)).strftime("%Y-%m-%d %H:%M:%S")
    with transacao(conn):
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        # faxina: registros antigos e sem bloqueio não servem mais
        conn.execute("DELETE FROM limite_acesso WHERE janela_inicio < ? AND (bloqueado_ate IS NULL OR bloqueado_ate < ?)",
                     ((datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), agora))
        linha = conn.execute("SELECT tentativas, janela_inicio, bloqueado_ate FROM limite_acesso WHERE chave = ?",
                             (chave,)).fetchone()
        bloqueio_vencido = linha is not None and bool(linha["bloqueado_ate"]) and linha["bloqueado_ate"] <= agora
        dentro_da_janela = linha is not None and linha["janela_inicio"] >= inicio_janela and not bloqueio_vencido
        total = linha["tentativas"] + 1 if dentro_da_janela else 1
        janela = linha["janela_inicio"] if dentro_da_janela else agora
        bloqueio = None
        if total == maximo:
            bloqueio = (datetime.now(timezone.utc) + timedelta(minutes=minutos_bloqueio)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO limite_acesso (chave, email, tentativas, janela_inicio, bloqueado_ate) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET tentativas = excluded.tentativas, janela_inicio = excluded.janela_inicio, "
            "bloqueado_ate = COALESCE(excluded.bloqueado_ate, bloqueado_ate)",
            (chave, email, total, janela, bloqueio),
        )
    return total


def registrar_tentativa(conn, chave: str, maximo: int, minutos_janela: int, minutos_bloqueio: int,
                        email: str | None = None) -> bool:
    """Como reservar_tentativa; devolve True quando a chave ficou bloqueada."""
    return reservar_tentativa(conn, chave, maximo, minutos_janela, minutos_bloqueio, email) >= maximo


# ---------------------------------------------------------------------------
# Usuários (o login é feito pelo Firebase: aqui só ficam o registro e o perfil)
# ---------------------------------------------------------------------------

EMAIL_USUARIO_API = "api@gptcode.local"

_SQL_USUARIO = (
    "SELECT id, nome, email, perfil, ativo, criado_em, ultimo_acesso_em, sessoes_validas_desde FROM usuario"
)


def _serializar_usuario(linha) -> dict:
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "email": linha["email"],
        "perfil": linha["perfil"],
        "perfil_rotulo": v.PERFIL_ROTULO[linha["perfil"]],
        "ativo": bool(linha["ativo"]),
        # cookies de sessão emitidos antes deste instante (epoch) não valem mais (logout)
        "sessoes_validas_desde": linha["sessoes_validas_desde"] or 0,
        "criado_em": linha["criado_em"],
        "ultimo_acesso_em": linha["ultimo_acesso_em"],
    }


def registrar_acesso_usuario(conn, email: str, nome: str, perfil: str = "admin") -> dict:
    """Primeiro acesso cria a conta; os seguintes só atualizam o nome e o último acesso."""
    email = email.strip().lower()
    with transacao(conn):
        conn.execute(
            "INSERT INTO usuario (nome, email, perfil, ultimo_acesso_em) VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(email) DO UPDATE SET nome = excluded.nome, ultimo_acesso_em = excluded.ultimo_acesso_em",
            ((nome or "").strip() or email, email, perfil),
        )
    return _serializar_usuario(conn.execute(f"{_SQL_USUARIO} WHERE email = ?", (email,)).fetchone())


def usuario_api(conn) -> dict:
    """Conta técnica usada para registrar a autoria das alterações feitas pelo token da API."""
    return registrar_acesso_usuario(conn, EMAIL_USUARIO_API, "Token da API", perfil="api")


def encerrar_sessoes(conn, usuario_id: int, desde: float) -> None:
    """Logout no servidor: invalida os cookies de sessão desta conta emitidos antes de `desde`."""
    with transacao(conn):
        conn.execute("UPDATE usuario SET sessoes_validas_desde = ? WHERE id = ?", (desde, usuario_id))


def obter_usuario(conn, usuario_id: int) -> dict:
    linha = conn.execute(f"{_SQL_USUARIO} WHERE id = ?", (usuario_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Usuário não encontrado.")
    return _serializar_usuario(linha)


def listar_usuarios(conn, incluir_api: bool = False) -> list[dict]:
    where = "" if incluir_api else "WHERE perfil <> 'api'"
    return [_serializar_usuario(r) for r in conn.execute(f"{_SQL_USUARIO} {where} ORDER BY ativo DESC, nome")]


def emails_administradores(conn) -> list[str]:
    return [r["email"] for r in conn.execute("SELECT email FROM usuario WHERE perfil = 'admin' AND ativo = 1")]


# ---------------------------------------------------------------------------
# Categorias de membro
# ---------------------------------------------------------------------------

def _serializar_categoria(linha) -> dict:
    return {
        "id": linha["id"],
        "slug": linha["slug"],
        "titulo": linha["titulo"],
        "mensagem_vazia": linha["mensagem_vazia"],
        "ordem_exibicao": linha["ordem_exibicao"],
        "total_membros": linha["total_membros"],
    }


_SQL_CATEGORIA = (
    "SELECT c.*, (SELECT COUNT(*) FROM membro m WHERE m.categoria_id = c.id) AS total_membros "
    "FROM categoria_membro c"
)


def listar_categorias(conn) -> list[dict]:
    return [
        _serializar_categoria(r)
        for r in conn.execute(f"{_SQL_CATEGORIA} ORDER BY c.ordem_exibicao, c.id")
    ]


def obter_categoria(conn, categoria_id: int) -> dict:
    linha = conn.execute(f"{_SQL_CATEGORIA} WHERE c.id = ?", (categoria_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Categoria não encontrada.")
    return _serializar_categoria(linha)


def criar_categoria(conn, dados: dict) -> dict:
    validado = v.validar_categoria(dados)
    with transacao(conn):
        ordem = validado["ordem_exibicao"]
        if ordem is None:
            ordem = _proxima_ordem(conn, "categoria_membro")
        cursor = conn.execute(
            "INSERT INTO categoria_membro (slug, titulo, mensagem_vazia, ordem_exibicao) "
            "VALUES (?, ?, ?, ?)",
            (validado["slug"], validado["titulo"], validado["mensagem_vazia"], ordem),
        )
    return obter_categoria(conn, cursor.lastrowid)


def atualizar_categoria(conn, categoria_id: int, dados: dict, parcial: bool = False) -> dict:
    atual = obter_categoria(conn, categoria_id)
    entrada = _mesclar(atual, dados) if parcial else {**dados, "slug": dados.get("slug") or atual["slug"]}
    validado = v.validar_categoria(entrada)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    with transacao(conn):
        conn.execute(
            "UPDATE categoria_membro SET slug = ?, titulo = ?, mensagem_vazia = ?, "
            "ordem_exibicao = ? WHERE id = ?",
            (validado["slug"], validado["titulo"], validado["mensagem_vazia"], ordem, categoria_id),
        )
    return obter_categoria(conn, categoria_id)


def remover_categoria(conn, categoria_id: int) -> None:
    categoria = obter_categoria(conn, categoria_id)
    if categoria["total_membros"]:
        raise Conflito(
            f"A categoria possui {categoria['total_membros']} membro(s). "
            "Mova-os para outra categoria antes de remove-la."
        )
    _impedir_exclusao_com_pendente(conn, None, categoria_id, "esta categoria", campo_dados="categoria_id")
    with transacao(conn):
        conn.execute("DELETE FROM categoria_membro WHERE id = ?", (categoria_id,))


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

_SQL_MEMBRO = (
    "SELECT m.*, c.slug AS categoria_slug, c.titulo AS categoria_titulo "
    "FROM membro m JOIN categoria_membro c ON c.id = m.categoria_id"
)


def _tags_por_membro(conn, ids: list[int]) -> dict[int, list[str]]:
    if not ids:
        return {}
    marcadores = ",".join("?" * len(ids))
    resultado: dict[int, list[str]] = {i: [] for i in ids}
    for linha in conn.execute(
        f"SELECT mt.membro_id, t.nome FROM membro_tag mt JOIN tag t ON t.id = mt.tag_id "
        f"WHERE mt.membro_id IN ({marcadores}) ORDER BY mt.membro_id, mt.ordem",
        ids,
    ):
        resultado[linha["membro_id"]].append(linha["nome"])
    return resultado


def _serializar_membro(linha, tags: list[str]) -> dict:
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "funcao": linha["funcao"],
        "email": linha["email"],
        "github_url": linha["github_url"],
        "lattes_url": linha["lattes_url"],
        "descricao": linha["descricao"],
        "foto": linha["foto"],
        "ativo": bool(linha["ativo"]),
        "ordem_exibicao": linha["ordem_exibicao"],
        "categoria_id": linha["categoria_id"],
        "categoria": {
            "id": linha["categoria_id"],
            "slug": linha["categoria_slug"],
            "titulo": linha["categoria_titulo"],
        },
        "tags": tags,
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def listar_membros(
    conn,
    categoria: str | int | None = None,
    apenas_ativos: bool = False,
) -> list[dict]:
    filtros, params = [], []
    if categoria is not None:
        categoria_id = v.converter_inteiro(categoria)
        if categoria_id is not None:
            filtros.append("m.categoria_id = ?")
            params.append(categoria_id)
        else:
            filtros.append("c.slug = ?")
            params.append(str(categoria))
    if apenas_ativos:
        filtros.append("m.ativo = 1")
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    linhas = conn.execute(
        f"{_SQL_MEMBRO} {where} ORDER BY c.ordem_exibicao, m.ordem_exibicao, m.id", params
    ).fetchall()
    tags = _tags_por_membro(conn, [linha["id"] for linha in linhas])
    return [_serializar_membro(linha, tags[linha["id"]]) for linha in linhas]


def obter_membro(conn, membro_id: int) -> dict:
    linha = conn.execute(f"{_SQL_MEMBRO} WHERE m.id = ?", (membro_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Membro não encontrado.")
    return _serializar_membro(linha, _tags_por_membro(conn, [membro_id])[membro_id])


def membro_para_entrada(membro: dict) -> dict:
    campos = ("categoria_id", "nome", "funcao", "email", "github_url", "lattes_url",
              "descricao", "ativo", "ordem_exibicao", "tags")
    return {campo: membro[campo] for campo in campos}


def _salvar_tags(conn, membro_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM membro_tag WHERE membro_id = ?", (membro_id,))
    for ordem, nome in enumerate(tags):
        conn.execute("INSERT INTO tag (nome) VALUES (?) ON CONFLICT(nome) DO NOTHING", (nome,))
        tag_id = conn.execute("SELECT id FROM tag WHERE nome = ?", (nome,)).fetchone()[0]
        conn.execute(
            "INSERT INTO membro_tag (membro_id, tag_id, ordem) VALUES (?, ?, ?)",
            (membro_id, tag_id, ordem),
        )


def _checar_categoria(conn, validado: dict) -> None:
    if not _existe(conn, "categoria_membro", validado["categoria_id"]):
        raise ValidacaoErro({"categoria_id": "Categoria inexistente."})


def _inserir_membro(conn, dados: dict, usuario_id: int | None, foto: str | None) -> int:
    validado = v.validar_membro(dados)
    _checar_categoria(conn, validado)
    ordem = validado["ordem_exibicao"]
    if ordem is None:
        ordem = _proxima_ordem(conn, "membro", "categoria_id = ?", (validado["categoria_id"],))
    cursor = conn.execute(
        "INSERT INTO membro (categoria_id, nome, funcao, email, github_url, lattes_url, "
        "descricao, foto, ativo, ordem_exibicao, atualizado_por) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (validado["categoria_id"], validado["nome"], validado["funcao"], validado["email"], validado["github_url"],
         validado["lattes_url"], validado["descricao"], foto, validado["ativo"], ordem, usuario_id),
    )
    _salvar_tags(conn, cursor.lastrowid, validado["tags"])
    return cursor.lastrowid


def _alterar_membro(conn, membro_id: int, dados: dict, usuario_id: int | None,
                    parcial: bool, foto: str | None) -> None:
    atual = obter_membro(conn, membro_id)
    entrada = _mesclar(membro_para_entrada(atual), dados) if parcial else dados
    validado = v.validar_membro(entrada)
    _checar_categoria(conn, validado)
    ordem = validado["ordem_exibicao"]
    if ordem is None:
        ordem = atual["ordem_exibicao"]
    conn.execute(
        "UPDATE membro SET categoria_id = ?, nome = ?, funcao = ?, email = ?, github_url = ?, "
        "lattes_url = ?, descricao = ?, ativo = ?, ordem_exibicao = ?, atualizado_por = ?, "
        "foto = COALESCE(?, foto) WHERE id = ?",
        (validado["categoria_id"], validado["nome"], validado["funcao"], validado["email"], validado["github_url"],
         validado["lattes_url"], validado["descricao"], validado["ativo"], ordem, usuario_id, foto, membro_id),
    )
    _salvar_tags(conn, membro_id, validado["tags"])


SEGUNDOS_ENVIO_REPETIDO = 600


def _chave_nome(nome: str) -> str:
    """Nome para comparar duplicidade: sem acento, sem diferença de caixa e de espaços."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def criar_membro(conn, dados: dict, usuario_id: int | None = None, foto: str | None = None) -> dict:
    validado = v.validar_membro(dados)
    with transacao(conn):
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")  # a checagem e a gravação não se separam (duplo clique simultâneo)
        # duplo clique / reenvio: o mesmo nome (sem acento, maiúsculas ou espaço extra) acabou de entrar
        desde = (datetime.now(timezone.utc) - timedelta(seconds=SEGUNDOS_ENVIO_REPETIDO)).strftime("%Y-%m-%d %H:%M:%S")
        chave = _chave_nome(validado["nome"])
        for (nome,) in conn.execute("SELECT nome FROM membro WHERE categoria_id = ? AND criado_em >= ?",
                                    (validado["categoria_id"], desde)):
            if _chave_nome(nome) == chave:
                raise Conflito(f"{validado['nome']} acabou de ser cadastrado(a) nesta categoria. O envio foi repetido?",
                               {"nome": "Este membro acabou de ser cadastrado."})
        novo_id = _inserir_membro(conn, dados, usuario_id, foto)
    return obter_membro(conn, novo_id)


def atualizar_membro(conn, membro_id: int, dados: dict, usuario_id: int | None = None,
                     parcial: bool = False, foto: str | None = None) -> dict:
    with transacao(conn):
        _alterar_membro(conn, membro_id, dados, usuario_id, parcial, foto)
    return obter_membro(conn, membro_id)


def definir_foto_membro(conn, membro_id: int, foto: str, usuario_id: int | None = None) -> str | None:
    """Troca a foto e devolve o caminho anterior (para apagar o arquivo)."""
    antiga = obter_membro(conn, membro_id)["foto"]
    with transacao(conn):
        conn.execute(
            "UPDATE membro SET foto = ?, atualizado_por = ? WHERE id = ?",
            (foto, usuario_id, membro_id),
        )
    return antiga


def _pendentes_que_usam(conn, campo: str, item_id: int) -> int:
    """Submissões pendentes de CRIAÇÃO cujos dados apontam para o item (categoria, projeto,
    orientador ou participante/autor membro). Se o item sumir, elas ficam impossíveis de aprovar."""
    total = 0
    for (texto,) in conn.execute("SELECT dados FROM submissao WHERE status = 'pendente'"):
        dados = json.loads(texto)
        if campo == "membro_id":
            citados = [dados.get("orientador_id")] + [
                p.get("membro_id") for p in (dados.get("participantes") or []) + (dados.get("autores") or [])
            ]
            total += item_id in citados
        else:
            total += dados.get(campo) == item_id
    return total


def _impedir_exclusao_com_pendente(conn, coluna: str | None, item_id: int, rotulo: str,
                                   campo_dados: str | None = None) -> None:
    """Uma submissão pendente (de link de edição, ou de criação que aponta para o item) seria
    apagada junto com o item ou ficaria impossível de aprovar, sem aviso a quem enviou.
    Exige avaliar a submissão antes de excluir."""
    pendentes = 0
    if coluna:
        pendentes += conn.execute(
            f"SELECT COUNT(*) FROM submissao s JOIN link_submissao l ON l.id = s.link_id "
            f"WHERE l.{coluna} = ? AND s.status = 'pendente'", (item_id,)
        ).fetchone()[0]
    if campo_dados:
        pendentes += _pendentes_que_usam(conn, campo_dados, item_id)
    if pendentes:
        raise Conflito(f"Há {pendentes} submissão(ões) pendente(s) para {rotulo}. "
                       "Aprove ou rejeite em Submissões pendentes antes de excluir.")


def remover_membro(conn, membro_id: int) -> dict:
    membro = obter_membro(conn, membro_id)
    _impedir_exclusao_com_pendente(conn, "membro_id", membro_id, "este membro", campo_dados="membro_id")
    orientados = conn.execute(
        "SELECT COUNT(*) FROM projeto WHERE orientador_id = ?", (membro_id,)
    ).fetchone()[0]
    if orientados:
        raise Conflito(
            f"{membro['nome']} orienta {orientados} projeto(s). "
            "Defina outro orientador nesses projetos antes de remover o membro."
        )
    with transacao(conn):
        conn.execute("DELETE FROM membro WHERE id = ?", (membro_id,))
    return membro


def listar_tags(conn) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT t.id, t.nome, COUNT(mt.membro_id) AS total_membros FROM tag t "
            "LEFT JOIN membro_tag mt ON mt.tag_id = t.id GROUP BY t.id ORDER BY t.nome"
        )
    ]


def _indice_nomes_membros(conn) -> dict[str, int]:
    """Nome normalizado -> id, apenas para nomes sem ambiguidade."""
    indice: dict[str, int] = {}
    repetidos: set[str] = set()
    for linha in conn.execute("SELECT id, nome FROM membro"):
        chave = v.normalizar_nome(linha["nome"])
        if chave in indice:
            repetidos.add(chave)
        indice[chave] = linha["id"]
    for chave in repetidos:
        indice.pop(chave, None)
    return indice


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

_SQL_PROJETO = (
    "SELECT p.*, o.nome AS orientador_nome FROM projeto p "
    "LEFT JOIN membro o ON o.id = p.orientador_id"
)


def _periodo(inicio: int | None, fim: int | None) -> str | None:
    if inicio is None:
        return None
    if fim is None or fim == inicio:
        return str(inicio)
    return f"{inicio}/{fim}"


def _participantes_por_projeto(conn, ids: list[int]) -> dict[int, list[dict]]:
    resultado: dict[int, list[dict]] = {i: [] for i in ids}
    if not ids:
        return resultado
    marcadores = ",".join("?" * len(ids))
    for linha in conn.execute(
        f"SELECT pp.*, m.nome AS membro_nome FROM projeto_participante pp "
        f"LEFT JOIN membro m ON m.id = pp.membro_id "
        f"WHERE pp.projeto_id IN ({marcadores}) ORDER BY pp.projeto_id, pp.ordem, pp.id",
        ids,
    ):
        resultado[linha["projeto_id"]].append(
            {
                "id": linha["id"],
                "membro_id": linha["membro_id"],
                "nome": linha["membro_nome"] if linha["membro_id"] else linha["nome_externo"],
                "papel": linha["papel"],
            }
        )
    return resultado


def _serializar_projeto(linha, participantes: list[dict]) -> dict:
    periodo = _periodo(linha["ano_inicio"], linha["ano_fim"])
    rotulo_modalidade = v.MODALIDADE_ROTULO[linha["modalidade"]]
    return {
        "id": linha["id"],
        "titulo": linha["titulo"],
        "modalidade": linha["modalidade"],
        "modalidade_rotulo": rotulo_modalidade,
        "status": linha["status"],
        "status_rotulo": v.STATUS_PROJETO_ROTULO[linha["status"]],
        "ano_inicio": linha["ano_inicio"],
        "ano_fim": linha["ano_fim"],
        "periodo": periodo,
        "rotulo": f"{rotulo_modalidade} {periodo}" if periodo else rotulo_modalidade,
        "descricao": linha["descricao"],
        "orientador_id": linha["orientador_id"],
        "orientador": (
            {"id": linha["orientador_id"], "nome": linha["orientador_nome"]}
            if linha["orientador_id"]
            else None
        ),
        "participantes": participantes,
        "ordem_exibicao": linha["ordem_exibicao"],
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def listar_projetos(conn, status: str | None = None, modalidade: str | None = None) -> list[dict]:
    filtros, params = [], []
    if status:
        filtros.append("p.status = ?")
        params.append(status)
    if modalidade:
        filtros.append("p.modalidade = ?")
        params.append(modalidade.upper())
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    linhas = conn.execute(f"{_SQL_PROJETO} {where} ORDER BY p.ordem_exibicao, p.id", params).fetchall()
    participantes = _participantes_por_projeto(conn, [linha["id"] for linha in linhas])
    return [_serializar_projeto(linha, participantes[linha["id"]]) for linha in linhas]


def obter_projeto(conn, projeto_id: int) -> dict:
    linha = conn.execute(f"{_SQL_PROJETO} WHERE p.id = ?", (projeto_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Projeto não encontrado.")
    return _serializar_projeto(linha, _participantes_por_projeto(conn, [projeto_id])[projeto_id])


def projeto_para_entrada(projeto: dict) -> dict:
    entrada = {
        campo: projeto[campo]
        for campo in ("titulo", "modalidade", "status", "ano_inicio", "ano_fim",
                      "descricao", "orientador_id", "ordem_exibicao")
    }
    entrada["participantes"] = [
        {"membro_id": p["membro_id"], "nome": None if p["membro_id"] else p["nome"], "papel": p["papel"]}
        for p in projeto["participantes"]
    ]
    return entrada


def _resolver_participantes(conn, participantes: list[dict]) -> list[tuple[int | None, str | None, str]]:
    indice = _indice_nomes_membros(conn)
    resolvidos, vistos = [], set()
    for posicao, p in enumerate(participantes, start=1):
        membro_id, nome = p["membro_id"], p["nome"]
        if membro_id is not None:
            if not _existe(conn, "membro", membro_id):
                raise ValidacaoErro({"participantes": f"Item {posicao}: membro {membro_id} não existe."})
            nome = None
        else:
            membro_id = indice.get(v.normalizar_nome(nome))
            if membro_id is not None:
                nome = None
        chave = membro_id if membro_id is not None else v.normalizar_nome(nome)
        if chave in vistos:
            raise ValidacaoErro({"participantes": f"Item {posicao}: participante repetido."})
        vistos.add(chave)
        resolvidos.append((membro_id, nome, p["papel"]))
    return resolvidos


def _salvar_participantes(conn, projeto_id: int, participantes: list[dict]) -> None:
    resolvidos = _resolver_participantes(conn, participantes)
    conn.execute("DELETE FROM projeto_participante WHERE projeto_id = ?", (projeto_id,))
    for ordem, (membro_id, nome, papel) in enumerate(resolvidos):
        conn.execute(
            "INSERT INTO projeto_participante (projeto_id, membro_id, nome_externo, papel, ordem) "
            "VALUES (?, ?, ?, ?, ?)",
            (projeto_id, membro_id, nome, papel, ordem),
        )


def _checar_orientador(conn, validado: dict) -> None:
    if validado["orientador_id"] is not None and not _existe(conn, "membro", validado["orientador_id"]):
        raise ValidacaoErro({"orientador_id": "Orientador inexistente."})


def _inserir_projeto(conn, dados: dict, usuario_id: int | None) -> int:
    validado = v.validar_projeto(dados)
    _checar_orientador(conn, validado)
    ordem = validado["ordem_exibicao"]
    if ordem is None:
        ordem = _proxima_ordem(conn, "projeto")
    cursor = conn.execute(
        "INSERT INTO projeto (titulo, modalidade, status, ano_inicio, ano_fim, descricao, "
        "orientador_id, ordem_exibicao, criado_por, atualizado_por) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (validado["titulo"], validado["modalidade"], validado["status"], validado["ano_inicio"], validado["ano_fim"],
         validado["descricao"], validado["orientador_id"], ordem, usuario_id, usuario_id),
    )
    _salvar_participantes(conn, cursor.lastrowid, validado["participantes"])
    return cursor.lastrowid


def _alterar_projeto(conn, projeto_id: int, dados: dict, usuario_id: int | None, parcial: bool) -> None:
    atual = obter_projeto(conn, projeto_id)
    entrada = _mesclar(projeto_para_entrada(atual), dados) if parcial else dados
    validado = v.validar_projeto(entrada)
    _checar_orientador(conn, validado)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    conn.execute(
        "UPDATE projeto SET titulo = ?, modalidade = ?, status = ?, ano_inicio = ?, ano_fim = ?, "
        "descricao = ?, orientador_id = ?, ordem_exibicao = ?, atualizado_por = ? WHERE id = ?",
        (validado["titulo"], validado["modalidade"], validado["status"], validado["ano_inicio"], validado["ano_fim"],
         validado["descricao"], validado["orientador_id"], ordem, usuario_id, projeto_id),
    )
    _salvar_participantes(conn, projeto_id, validado["participantes"])


def criar_projeto(conn, dados: dict, usuario_id: int | None = None) -> dict:
    with transacao(conn):
        novo_id = _inserir_projeto(conn, dados, usuario_id)
    return obter_projeto(conn, novo_id)


def atualizar_projeto(conn, projeto_id: int, dados: dict, usuario_id: int | None = None,
                      parcial: bool = False) -> dict:
    with transacao(conn):
        _alterar_projeto(conn, projeto_id, dados, usuario_id, parcial)
    return obter_projeto(conn, projeto_id)


def remover_projeto(conn, projeto_id: int) -> dict:
    projeto = obter_projeto(conn, projeto_id)
    _impedir_exclusao_com_pendente(conn, "projeto_id", projeto_id, "este projeto", campo_dados="projeto_id")
    with transacao(conn):
        conn.execute("DELETE FROM projeto WHERE id = ?", (projeto_id,))
    return projeto


# ---------------------------------------------------------------------------
# Publicacoes
# ---------------------------------------------------------------------------

_SQL_PUBLICACAO = (
    "SELECT pub.*, p.titulo AS projeto_titulo FROM publicacao pub "
    "LEFT JOIN projeto p ON p.id = pub.projeto_id"
)


def _autores_por_publicacao(conn, ids: list[int]) -> dict[int, list[dict]]:
    resultado: dict[int, list[dict]] = {i: [] for i in ids}
    if not ids:
        return resultado
    marcadores = ",".join("?" * len(ids))
    for linha in conn.execute(
        f"SELECT * FROM publicacao_autor WHERE publicacao_id IN ({marcadores}) "
        f"ORDER BY publicacao_id, ordem",
        ids,
    ):
        resultado[linha["publicacao_id"]].append(
            {"ordem": linha["ordem"], "nome_citacao": linha["nome_citacao"], "membro_id": linha["membro_id"]}
        )
    return resultado


def _serializar_publicacao(linha, autores: list[dict]) -> dict:
    doi_url = f"https://doi.org/{linha['doi']}" if linha["doi"] else None
    return {
        "id": linha["id"],
        "titulo": linha["titulo"],
        "ano": linha["ano"],
        "tipo": linha["tipo"],
        "tipo_rotulo": v.TIPO_PUBLICACAO_ROTULO[linha["tipo"]],
        "veiculo": linha["veiculo"],
        "doi": linha["doi"],
        "doi_url": doi_url,
        "url": linha["url"],
        "link": doi_url or linha["url"],
        "projeto_id": linha["projeto_id"],
        "projeto": (
            {"id": linha["projeto_id"], "titulo": linha["projeto_titulo"]} if linha["projeto_id"] else None
        ),
        "autores": autores,
        "autores_texto": "; ".join(a["nome_citacao"] for a in autores),
        "ordem_exibicao": linha["ordem_exibicao"],
        "criado_em": linha["criado_em"],
        "atualizado_em": linha["atualizado_em"],
    }


def listar_publicacoes(conn, ano: int | None = None, tipo: str | None = None,
                       projeto_id: int | None = None) -> list[dict]:
    filtros, params = [], []
    if ano is not None:
        filtros.append("pub.ano = ?")
        params.append(ano)
    if tipo:
        filtros.append("pub.tipo = ?")
        params.append(tipo)
    if projeto_id is not None:
        filtros.append("pub.projeto_id = ?")
        params.append(projeto_id)
    where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
    linhas = conn.execute(
        f"{_SQL_PUBLICACAO} {where} ORDER BY pub.ano DESC, pub.ordem_exibicao, pub.id", params
    ).fetchall()
    autores = _autores_por_publicacao(conn, [linha["id"] for linha in linhas])
    return [_serializar_publicacao(linha, autores[linha["id"]]) for linha in linhas]


def obter_publicacao(conn, publicacao_id: int) -> dict:
    linha = conn.execute(f"{_SQL_PUBLICACAO} WHERE pub.id = ?", (publicacao_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Publicação não encontrada.")
    return _serializar_publicacao(linha, _autores_por_publicacao(conn, [publicacao_id])[publicacao_id])


def publicacao_para_entrada(publicacao: dict) -> dict:
    entrada = {
        campo: publicacao[campo]
        for campo in ("titulo", "ano", "tipo", "veiculo", "doi", "url", "projeto_id", "ordem_exibicao")
    }
    entrada["autores"] = [
        {"nome": a["nome_citacao"], "membro_id": a["membro_id"]} for a in publicacao["autores"]
    ]
    return entrada


def _checar_publicacao(conn, validado: dict) -> None:
    if validado["projeto_id"] is not None and not _existe(conn, "projeto", validado["projeto_id"]):
        raise ValidacaoErro({"projeto_id": "Projeto inexistente."})
    vistos = set()
    for autor in validado["autores"]:
        membro_id = autor["membro_id"]
        if membro_id is None:
            continue
        if not _existe(conn, "membro", membro_id):
            raise ValidacaoErro({"autores": f"Membro {membro_id} não existe."})
        if membro_id in vistos:
            raise ValidacaoErro({"autores": "O mesmo membro foi informado mais de uma vez."})
        vistos.add(membro_id)


def _salvar_autores(conn, publicacao_id: int, autores: list[dict]) -> None:
    conn.execute("DELETE FROM publicacao_autor WHERE publicacao_id = ?", (publicacao_id,))
    for ordem, autor in enumerate(autores, start=1):
        conn.execute(
            "INSERT INTO publicacao_autor (publicacao_id, ordem, nome_citacao, membro_id) "
            "VALUES (?, ?, ?, ?)",
            (publicacao_id, ordem, autor["nome_citacao"], autor["membro_id"]),
        )


def _inserir_publicacao(conn, dados: dict, usuario_id: int | None) -> int:
    validado = v.validar_publicacao(dados)
    _checar_publicacao(conn, validado)
    ordem = validado["ordem_exibicao"]
    if ordem is None:
        ordem = _proxima_ordem(conn, "publicacao")
    cursor = conn.execute(
        "INSERT INTO publicacao (titulo, ano, tipo, veiculo, doi, url, projeto_id, "
        "ordem_exibicao, criado_por, atualizado_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (validado["titulo"], validado["ano"], validado["tipo"], validado["veiculo"], validado["doi"], validado["url"],
         validado["projeto_id"], ordem, usuario_id, usuario_id),
    )
    _salvar_autores(conn, cursor.lastrowid, validado["autores"])
    return cursor.lastrowid


def _alterar_publicacao(conn, publicacao_id: int, dados: dict, usuario_id: int | None, parcial: bool) -> None:
    atual = obter_publicacao(conn, publicacao_id)
    entrada = _mesclar(publicacao_para_entrada(atual), dados) if parcial else dados
    validado = v.validar_publicacao(entrada)
    _checar_publicacao(conn, validado)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    conn.execute(
        "UPDATE publicacao SET titulo = ?, ano = ?, tipo = ?, veiculo = ?, doi = ?, url = ?, "
        "projeto_id = ?, ordem_exibicao = ?, atualizado_por = ? WHERE id = ?",
        (validado["titulo"], validado["ano"], validado["tipo"], validado["veiculo"], validado["doi"], validado["url"],
         validado["projeto_id"], ordem, usuario_id, publicacao_id),
    )
    _salvar_autores(conn, publicacao_id, validado["autores"])


def criar_publicacao(conn, dados: dict, usuario_id: int | None = None) -> dict:
    with transacao(conn):
        novo_id = _inserir_publicacao(conn, dados, usuario_id)
    return obter_publicacao(conn, novo_id)


def atualizar_publicacao(conn, publicacao_id: int, dados: dict, usuario_id: int | None = None,
                         parcial: bool = False) -> dict:
    with transacao(conn):
        _alterar_publicacao(conn, publicacao_id, dados, usuario_id, parcial)
    return obter_publicacao(conn, publicacao_id)


def remover_publicacao(conn, publicacao_id: int) -> dict:
    publicacao = obter_publicacao(conn, publicacao_id)
    _impedir_exclusao_com_pendente(conn, "publicacao_id", publicacao_id, "esta publicação")
    with transacao(conn):
        conn.execute("DELETE FROM publicacao WHERE id = ?", (publicacao_id,))
    return publicacao


# ---------------------------------------------------------------------------
# Contatos
# ---------------------------------------------------------------------------

def _serializar_contato(linha) -> dict:
    dados = dict(linha)
    dados["tipo_rotulo"] = v.TIPO_CONTATO_ROTULO[linha["tipo"]]
    dados.pop("atualizado_por", None)
    return dados


def listar_contatos(conn) -> list[dict]:
    return [_serializar_contato(r) for r in conn.execute("SELECT * FROM contato ORDER BY ordem_exibicao, id")]


def obter_contato(conn, contato_id: int) -> dict:
    linha = conn.execute("SELECT * FROM contato WHERE id = ?", (contato_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Contato não encontrado.")
    return _serializar_contato(linha)


_CAMPOS_CONTATO = ("tipo", "titulo", "valor", "subtitulo", "link", "icone", "ordem_exibicao")


def criar_contato(conn, dados: dict, usuario_id: int | None = None) -> dict:
    validado = v.validar_contato(dados)
    with transacao(conn):
        ordem = validado["ordem_exibicao"]
        if ordem is None:
            ordem = _proxima_ordem(conn, "contato")
        cursor = conn.execute(
            "INSERT INTO contato (tipo, titulo, valor, subtitulo, link, icone, ordem_exibicao, "
            "atualizado_por) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (validado["tipo"], validado["titulo"], validado["valor"], validado["subtitulo"], validado["link"], validado["icone"], ordem, usuario_id),
        )
    return obter_contato(conn, cursor.lastrowid)


def atualizar_contato(conn, contato_id: int, dados: dict, usuario_id: int | None = None,
                      parcial: bool = False) -> dict:
    atual = obter_contato(conn, contato_id)
    entrada = _mesclar({c: atual[c] for c in _CAMPOS_CONTATO}, dados) if parcial else dados
    validado = v.validar_contato(entrada)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    with transacao(conn):
        conn.execute(
            "UPDATE contato SET tipo = ?, titulo = ?, valor = ?, subtitulo = ?, link = ?, icone = ?, "
            "ordem_exibicao = ?, atualizado_por = ? WHERE id = ?",
            (validado["tipo"], validado["titulo"], validado["valor"], validado["subtitulo"], validado["link"], validado["icone"],
             ordem, usuario_id, contato_id),
        )
    return obter_contato(conn, contato_id)


def remover_contato(conn, contato_id: int) -> None:
    obter_contato(conn, contato_id)
    with transacao(conn):
        conn.execute("DELETE FROM contato WHERE id = ?", (contato_id,))


# ---------------------------------------------------------------------------
# Mensagens do formulario de contato
# ---------------------------------------------------------------------------

def _serializar_mensagem(linha) -> dict:
    dados = dict(linha)
    dados["lida"] = bool(dados["lida"])
    return dados


# Anti-spam do formulário público de contato (por IP).
MAX_MENSAGENS_POR_IP = 5
MINUTOS_JANELA_MENSAGENS = 10
MAX_MENSAGENS_POR_HORA = 200


def criar_mensagem(conn, dados: dict, ip: str | None = None) -> dict:
    """Grava a mensagem do formulário de contato.

    * no máximo 5 mensagens a cada 10 minutos por IP (LimiteExcedido, HTTP 429);
    * a mesma mensagem do mesmo e-mail reenviada em até 10 minutos (duplo clique,
      botão voltar) não é gravada de novo: devolve a que já existe."""
    chave = f"contato:{rede_do_ip(ip)}"
    minutos = max(minutos_bloqueado(conn, chave), minutos_bloqueado(conn, "contato-global"))
    if minutos:
        raise LimiteExcedido(f"Você enviou muitas mensagens seguidas. Tente novamente em {minutos} minuto(s).")
    validado = v.validar_mensagem(dados)
    repetida = conn.execute(
        "SELECT id FROM mensagem_contato WHERE email_remetente = ? AND mensagem = ? AND recebida_em >= ?",
        (validado["email_remetente"], validado["mensagem"],
         (datetime.now(timezone.utc) - timedelta(minutes=MINUTOS_JANELA_MENSAGENS)).strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchone()
    if repetida:
        return obter_mensagem(conn, repetida["id"])
    with transacao(conn):
        cursor = conn.execute(
            "INSERT INTO mensagem_contato (nome_remetente, email_remetente, assunto, mensagem) "
            "VALUES (?, ?, ?, ?)",
            (validado["nome_remetente"], validado["email_remetente"], validado["assunto"], validado["mensagem"]),
        )
    registrar_tentativa(conn, chave, MAX_MENSAGENS_POR_IP, MINUTOS_JANELA_MENSAGENS, MINUTOS_JANELA_MENSAGENS)
    # teto geral por hora: quem troca de endereço o tempo todo ainda esbarra aqui
    registrar_tentativa(conn, "contato-global", MAX_MENSAGENS_POR_HORA, 60, 60)
    return obter_mensagem(conn, cursor.lastrowid)


def importar_mensagem(conn, mensagem: dict) -> None:
    """Grava uma mensagem vinda do banco antigo (v1), mantendo a data e o estado de leitura."""
    with transacao(conn):
        conn.execute(
            "INSERT INTO mensagem_contato (nome_remetente, email_remetente, mensagem, lida, recebida_em) "
            "VALUES (?, ?, ?, ?, ?)",
            (mensagem["nome"], mensagem["email"], mensagem["mensagem"],
             1 if mensagem.get("lido") else 0, mensagem["enviado_em"]),
        )


def listar_mensagens(conn, apenas_nao_lidas: bool = False) -> list[dict]:
    where = "WHERE lida = 0" if apenas_nao_lidas else ""
    return [
        _serializar_mensagem(r)
        for r in conn.execute(f"SELECT * FROM mensagem_contato {where} ORDER BY recebida_em DESC, id DESC")
    ]


def obter_mensagem(conn, mensagem_id: int) -> dict:
    linha = conn.execute("SELECT * FROM mensagem_contato WHERE id = ?", (mensagem_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Mensagem não encontrada.")
    return _serializar_mensagem(linha)


def marcar_mensagem(conn, mensagem_id: int, lida: bool = True) -> dict:
    obter_mensagem(conn, mensagem_id)
    with transacao(conn):
        conn.execute("UPDATE mensagem_contato SET lida = ? WHERE id = ?", (1 if lida else 0, mensagem_id))
    return obter_mensagem(conn, mensagem_id)


def remover_mensagem(conn, mensagem_id: int) -> None:
    obter_mensagem(conn, mensagem_id)
    with transacao(conn):
        conn.execute("DELETE FROM mensagem_contato WHERE id = ?", (mensagem_id,))


def contar_mensagens_nao_lidas(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM mensagem_contato WHERE lida = 0").fetchone()[0]


# ---------------------------------------------------------------------------
# Pagina inicial: slider, parceiros, configuracoes e destaque
# ---------------------------------------------------------------------------

def listar_slider(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM slider_imagem ORDER BY ordem_exibicao, id")]


def obter_slider(conn, slide_id: int) -> dict:
    linha = conn.execute("SELECT * FROM slider_imagem WHERE id = ?", (slide_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Imagem do slider não encontrada.")
    return dict(linha)


def criar_slider(conn, dados: dict, imagem: str) -> dict:
    validado = v.validar_slider(dados)
    with transacao(conn):
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT 1 FROM slider_imagem WHERE texto_alternativo = ? COLLATE NOCASE",
                        (validado["texto_alternativo"],)).fetchone():
            raise Conflito("Já existe uma imagem no slider com esta descrição (o envio foi repetido?).",
                           {"texto_alternativo": "Já existe uma imagem com esta descrição."})
        ordem = validado["ordem_exibicao"]
        if ordem is None:
            ordem = _proxima_ordem(conn, "slider_imagem")
        cursor = conn.execute(
            "INSERT INTO slider_imagem (imagem, texto_alternativo, ordem_exibicao) VALUES (?, ?, ?)",
            (imagem, validado["texto_alternativo"], ordem),
        )
    return obter_slider(conn, cursor.lastrowid)


def atualizar_slider(conn, slide_id: int, dados: dict, imagem: str | None = None,
                     parcial: bool = False) -> tuple[dict, str | None]:
    """Retorna (registro atualizado, imagem antiga a apagar ou None)."""
    atual = obter_slider(conn, slide_id)
    entrada = _mesclar(atual, dados) if parcial else dados
    validado = v.validar_slider(entrada)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    with transacao(conn):
        conn.execute(
            "UPDATE slider_imagem SET texto_alternativo = ?, ordem_exibicao = ?, "
            "imagem = COALESCE(?, imagem) WHERE id = ?",
            (validado["texto_alternativo"], ordem, imagem, slide_id),
        )
    return obter_slider(conn, slide_id), (atual["imagem"] if imagem else None)


def remover_slider(conn, slide_id: int) -> dict:
    slide = obter_slider(conn, slide_id)
    with transacao(conn):
        conn.execute("DELETE FROM slider_imagem WHERE id = ?", (slide_id,))
    return slide


def listar_parceiros(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM parceiro ORDER BY ordem_exibicao, id")]


def obter_parceiro(conn, parceiro_id: int) -> dict:
    linha = conn.execute("SELECT * FROM parceiro WHERE id = ?", (parceiro_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Parceiro não encontrado.")
    return dict(linha)


def criar_parceiro(conn, dados: dict, logo: str) -> dict:
    validado = v.validar_parceiro(dados)
    with transacao(conn):
        ordem = validado["ordem_exibicao"]
        if ordem is None:
            ordem = _proxima_ordem(conn, "parceiro")
        cursor = conn.execute(
            "INSERT INTO parceiro (nome, link, logo, ordem_exibicao) VALUES (?, ?, ?, ?)",
            (validado["nome"], validado["link"], logo, ordem),
        )
    return obter_parceiro(conn, cursor.lastrowid)


def atualizar_parceiro(conn, parceiro_id: int, dados: dict, logo: str | None = None,
                       parcial: bool = False) -> tuple[dict, str | None]:
    atual = obter_parceiro(conn, parceiro_id)
    entrada = _mesclar(atual, dados) if parcial else dados
    validado = v.validar_parceiro(entrada)
    ordem = validado["ordem_exibicao"] if validado["ordem_exibicao"] is not None else atual["ordem_exibicao"]
    with transacao(conn):
        conn.execute(
            "UPDATE parceiro SET nome = ?, link = ?, ordem_exibicao = ?, logo = COALESCE(?, logo) "
            "WHERE id = ?",
            (validado["nome"], validado["link"], ordem, logo, parceiro_id),
        )
    return obter_parceiro(conn, parceiro_id), (atual["logo"] if logo else None)


def remover_parceiro(conn, parceiro_id: int) -> dict:
    parceiro = obter_parceiro(conn, parceiro_id)
    with transacao(conn):
        conn.execute("DELETE FROM parceiro WHERE id = ?", (parceiro_id,))
    return parceiro


def obter_configuracoes(conn) -> dict[str, str]:
    valores = {chave: "" for chave in v.CHAVES_CONFIGURACAO}
    for linha in conn.execute("SELECT chave, valor FROM configuracao"):
        if linha["chave"] in valores:
            valores[linha["chave"]] = linha["valor"]
    return valores


def atualizar_configuracoes(conn, dados: dict, usuario_id: int | None = None) -> dict[str, str]:
    validado = v.validar_configuracoes(dados)
    with transacao(conn):
        for chave, valor in validado.items():
            conn.execute(
                "INSERT INTO configuracao (chave, valor, atualizado_por) VALUES (?, ?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, "
                "atualizado_por = excluded.atualizado_por, atualizado_em = datetime('now')",
                (chave, valor, usuario_id),
            )
    return obter_configuracoes(conn)


def obter_destaque(conn) -> dict:
    linha = conn.execute("SELECT projeto_id, publicacao_id FROM destaque WHERE id = 1").fetchone()
    if linha and linha["projeto_id"]:
        return {"tipo": "projeto", "item_id": linha["projeto_id"], "item": obter_projeto(conn, linha["projeto_id"])}
    if linha and linha["publicacao_id"]:
        return {
            "tipo": "publicacao",
            "item_id": linha["publicacao_id"],
            "item": obter_publicacao(conn, linha["publicacao_id"]),
        }
    return {"tipo": "nenhum", "item_id": None, "item": None}


def definir_destaque(conn, dados: dict) -> dict:
    validado = v.validar_destaque(dados)
    if validado["projeto_id"] is not None and not _existe(conn, "projeto", validado["projeto_id"]):
        raise ValidacaoErro({"item_id": "Projeto inexistente."})
    if validado["publicacao_id"] is not None and not _existe(conn, "publicacao", validado["publicacao_id"]):
        raise ValidacaoErro({"item_id": "Publicação inexistente."})
    with transacao(conn):
        conn.execute(
            "INSERT INTO destaque (id, projeto_id, publicacao_id) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET projeto_id = excluded.projeto_id, "
            "publicacao_id = excluded.publicacao_id",
            (validado["projeto_id"], validado["publicacao_id"]),
        )
    return obter_destaque(conn)


# ---------------------------------------------------------------------------
# Links de uso unico e submissoes
# ---------------------------------------------------------------------------

_COLUNA_ALVO = {"projeto": "projeto_id", "publicacao": "publicacao_id", "membro": "membro_id"}
_OBTER_ALVO = {"projeto": obter_projeto, "publicacao": obter_publicacao, "membro": obter_membro}


def _serializar_link(linha) -> dict:
    agora = agora_sql()
    if linha["usado_em"]:
        situacao = "usado"
    elif linha["expira_em"] <= agora:
        situacao = "expirado"
    else:
        situacao = "ativo"
    return {
        "id": linha["id"],
        "recurso": linha["recurso"],
        "acao": linha["acao"],
        "item_id": linha[_COLUNA_ALVO[linha["recurso"]]],
        "criado_em": linha["criado_em"],
        "expira_em": linha["expira_em"],
        "usado_em": linha["usado_em"],
        "situacao": situacao,
    }


def gerar_link(conn, dados: dict, usuario_id: int | None = None) -> dict:
    """Cria um link de uso unico. O token so e devolvido aqui (no banco fica o hash)."""
    validado = v.validar_link(dados)
    if validado["acao"] == "editar":
        _OBTER_ALVO[validado["recurso"]](conn, validado["item_id"])  # 404 se o alvo nao existir
    token = secrets.token_urlsafe(32)
    alvos = {"projeto_id": None, "publicacao_id": None, "membro_id": None}
    if validado["item_id"] is not None:
        alvos[_COLUNA_ALVO[validado["recurso"]]] = validado["item_id"]
    with transacao(conn):
        cursor = conn.execute(
            "INSERT INTO link_submissao (token_hash, recurso, acao, projeto_id, publicacao_id, "
            "membro_id, criado_por, criado_em, expira_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_hash_token(token), validado["recurso"], validado["acao"], alvos["projeto_id"],
             alvos["publicacao_id"], alvos["membro_id"], usuario_id, agora_sql(),
             agora_sql(validado["validade_dias"])),
        )
    linha = conn.execute("SELECT * FROM link_submissao WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return {**_serializar_link(linha), "token": token}


def listar_links(conn, apenas_ativos: bool = False) -> list[dict]:
    links = [_serializar_link(r) for r in conn.execute("SELECT * FROM link_submissao ORDER BY id DESC")]
    if apenas_ativos:
        links = [linha for linha in links if linha["situacao"] == "ativo"]
    return links


def revogar_link(conn, link_id: int) -> None:
    linha = conn.execute("SELECT * FROM link_submissao WHERE id = ?", (link_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Link não encontrado.")
    if linha["usado_em"]:
        raise Conflito("Este link já foi utilizado; a submissão gerada fica no histórico.")
    with transacao(conn):
        conn.execute("DELETE FROM link_submissao WHERE id = ?", (link_id,))


def buscar_link_ativo(conn, token: str, recurso: str) -> dict | None:
    """Link ativo para o recurso informado, ou None (inexistente/usado/expirado/outro recurso)."""
    linha = conn.execute(
        "SELECT * FROM link_submissao WHERE token_hash = ?", (_hash_token(token),)
    ).fetchone()
    if not linha or linha["recurso"] != recurso:
        return None
    link = _serializar_link(linha)
    return link if link["situacao"] == "ativo" else None


def registrar_submissao(conn, link: dict, dados: dict) -> int:
    """Grava a submissao e consome o link na mesma transacao."""
    with transacao(conn):
        consumido = conn.execute(
            "UPDATE link_submissao SET usado_em = ? WHERE id = ? AND usado_em IS NULL AND expira_em > ?",
            (agora_sql(), link["id"], agora_sql()),
        ).rowcount
        if consumido != 1:
            raise Conflito("Este link já foi utilizado ou expirou.")
        cursor = conn.execute(
            "INSERT INTO submissao (link_id, dados) VALUES (?, ?)",
            (link["id"], json.dumps(dados, ensure_ascii=False)),
        )
    return cursor.lastrowid


def _serializar_submissao(conn, linha) -> dict:
    recurso = linha["recurso"]
    item_id = linha[_COLUNA_ALVO[recurso]]
    atual = None
    if item_id is not None:
        try:
            atual = _OBTER_ALVO[recurso](conn, item_id)
        except NaoEncontrado:
            atual = None
    return {
        "id": linha["id"],
        "status": linha["status"],
        "recurso": recurso,
        "acao": linha["acao"],
        "item_id": item_id,
        "dados": json.loads(linha["dados"]),
        "atual": atual,
        "enviada_em": linha["enviada_em"],
        "avaliada_em": linha["avaliada_em"],
        "avaliada_por": linha["avaliada_por"],
    }


_SQL_SUBMISSAO = (
    "SELECT s.*, l.recurso, l.acao, l.projeto_id, l.publicacao_id, l.membro_id "
    "FROM submissao s JOIN link_submissao l ON l.id = s.link_id"
)


def listar_submissoes(conn, status: str | None = "pendente", limite: int | None = None) -> list[dict]:
    where, params = ("WHERE s.status = ?", [status]) if status else ("", [])
    sql_limite = ""
    if limite is not None:
        sql_limite, params = " LIMIT ?", [*params, limite]
    return [
        _serializar_submissao(conn, r)
        for r in conn.execute(f"{_SQL_SUBMISSAO} {where} ORDER BY s.enviada_em DESC, s.id DESC{sql_limite}", params)
    ]


def obter_submissao(conn, submissao_id: int) -> dict:
    linha = conn.execute(f"{_SQL_SUBMISSAO} WHERE s.id = ?", (submissao_id,)).fetchone()
    if not linha:
        raise NaoEncontrado("Submissão não encontrada.")
    return _serializar_submissao(conn, linha)


def contar_submissoes_pendentes(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM submissao WHERE status = 'pendente'").fetchone()[0]


def _aplicar_submissao(conn, recurso: str, acao: str, item_id: int | None,
                       dados: dict, usuario_id: int | None) -> int:
    """Grava os dados de uma submissao (sem transacao propria). Retorna o id do item."""
    dados = dict(dados)
    foto = dados.pop("foto", None) if recurso == "membro" else None
    if recurso == "membro":
        if acao == "criar":
            return _inserir_membro(conn, dados, usuario_id, foto)
        _alterar_membro(conn, item_id, dados, usuario_id, parcial=True, foto=foto)
    elif recurso == "projeto":
        if acao == "criar":
            return _inserir_projeto(conn, dados, usuario_id)
        _alterar_projeto(conn, item_id, dados, usuario_id, parcial=True)
    else:
        if acao == "criar":
            return _inserir_publicacao(conn, dados, usuario_id)
        _alterar_publicacao(conn, item_id, dados, usuario_id, parcial=True)
    return item_id


class _Simulacao(Exception):
    pass


def simular_submissao(conn, recurso: str, acao: str, item_id: int | None, dados: dict) -> None:
    """Executa a gravacao e desfaz (rollback), so para revelar erros de validacao
    ou de integridade (ex.: titulo duplicado) antes de consumir o link."""
    try:
        with transacao(conn):
            _aplicar_submissao(conn, recurso, acao, item_id, dados, None)
            raise _Simulacao
    except _Simulacao:
        pass


def _avaliar(conn, submissao_id: int, status: str, usuario_id: int | None) -> None:
    """Marca a submissão como avaliada só se ainda estiver pendente (dois cliques simultâneos
    em "Aprovar" não aplicam o cadastro duas vezes). Se a aplicação falhar depois, a
    transação inteira volta atrás."""
    cursor = conn.execute(
        "UPDATE submissao SET status = ?, avaliada_em = datetime('now'), avaliada_por = ? "
        "WHERE id = ? AND status = 'pendente'",
        (status, usuario_id, submissao_id),
    )
    if cursor.rowcount == 0:
        raise Conflito("Esta submissão já foi avaliada.")


def aprovar_submissao(conn, submissao_id: int, usuario_id: int | None = None) -> dict:
    """Aplica a submissao (criar/editar) e marca como aprovada, atomicamente.

    Os dados sao validados de novo aqui: o cadastro pode ter mudado desde o
    envio (ex.: outro projeto com o mesmo titulo foi criado).
    """
    submissao = obter_submissao(conn, submissao_id)
    if submissao["status"] != "pendente":
        raise Conflito("Esta submissão já foi avaliada.")

    with transacao(conn):
        _avaliar(conn, submissao_id, "aprovada", usuario_id)  # reserva primeiro: só um "Aprovar" passa
        item_id = _aplicar_submissao(
            conn, submissao["recurso"], submissao["acao"], submissao["item_id"],
            submissao["dados"], usuario_id,
        )
    resultado = obter_submissao(conn, submissao_id)
    resultado["item_id"] = item_id
    return resultado


def rejeitar_submissao(conn, submissao_id: int, usuario_id: int | None = None) -> dict:
    submissao = obter_submissao(conn, submissao_id)
    if submissao["status"] != "pendente":
        raise Conflito("Esta submissão já foi avaliada.")
    with transacao(conn):
        _avaliar(conn, submissao_id, "rejeitada", usuario_id)
    return obter_submissao(conn, submissao_id)


# ---------------------------------------------------------------------------
# Indicadores do dashboard
# ---------------------------------------------------------------------------

def estatisticas(conn) -> dict[str, int]:
    def contar(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    return {
        "slider": contar("SELECT COUNT(*) FROM slider_imagem"),
        "parceiros": contar("SELECT COUNT(*) FROM parceiro"),
        "projetos": contar("SELECT COUNT(*) FROM projeto"),
        "publicacoes": contar("SELECT COUNT(*) FROM publicacao"),
        "membros": contar("SELECT COUNT(*) FROM membro"),
        "categorias": contar("SELECT COUNT(*) FROM categoria_membro"),
        "contatos": contar("SELECT COUNT(*) FROM contato"),
        "mensagens_nao_lidas": contar_mensagens_nao_lidas(conn),
        "submissoes_pendentes": contar_submissoes_pendentes(conn),
    }
