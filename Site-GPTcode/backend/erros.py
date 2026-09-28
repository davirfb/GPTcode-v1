"""Excecoes de dominio compartilhadas pelo painel, pela API e pelos links."""

from __future__ import annotations

import re
import sqlite3


class ErroDominio(Exception):
    status_http = 400

    def __init__(self, mensagem: str, campos: dict[str, str] | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campos = campos or {}

    def como_dict(self) -> dict:
        corpo = {"erro": self.mensagem}
        if self.campos:
            corpo["campos"] = self.campos
        return corpo

    def mensagens(self) -> list[str]:
        """Lista legivel para exibir no painel (flash)."""
        if not self.campos:
            return [self.mensagem]
        return [f"{campo}: {texto}" for campo, texto in self.campos.items()]


class ValidacaoErro(ErroDominio):
    """Dados que violam regras de negocio (HTTP 422)."""

    status_http = 422

    def __init__(self, campos: dict[str, str], mensagem: str = "Dados invalidos."):
        super().__init__(mensagem, campos)


class NaoEncontrado(ErroDominio):
    status_http = 404


class Conflito(ErroDominio):
    """Violacao de unicidade ou registro em uso por outro (HTTP 409)."""

    status_http = 409


# Mensagens amigaveis para as restricoes UNIQUE do schema.
_MENSAGENS_UNIQUE = {
    "usuario.email": ("email", "Ja existe um usuario com este e-mail."),
    "categoria_membro.slug": ("slug", "Ja existe uma categoria com este identificador."),
    "categoria_membro.titulo": ("titulo", "Ja existe uma categoria com este titulo."),
    "membro.email": ("email", "Ja existe um membro com este e-mail."),
    "projeto.titulo": ("titulo", "Ja existe um projeto com este titulo."),
    "projeto_participante.projeto_id, projeto_participante.membro_id": (
        "participantes",
        "O mesmo membro foi informado mais de uma vez.",
    ),
    "projeto_participante.projeto_id, projeto_participante.nome_externo": (
        "participantes",
        "O mesmo participante foi informado mais de uma vez.",
    ),
    "publicacao.doi": ("doi", "Ja existe uma publicacao com este DOI."),
    "publicacao.titulo, publicacao.ano": (
        "titulo",
        "Ja existe uma publicacao com este titulo neste ano.",
    ),
    "publicacao_autor.publicacao_id, publicacao_autor.membro_id": (
        "autores",
        "O mesmo membro foi informado mais de uma vez como autor.",
    ),
    "contato.tipo, contato.valor": ("valor", "Este canal de contato ja esta cadastrado."),
    "parceiro.nome": ("nome", "Ja existe um parceiro com este nome."),
    "slider_imagem.imagem": ("imagem", "Esta imagem ja esta no slider."),
}


def traduzir_integridade(exc: sqlite3.IntegrityError) -> ErroDominio:
    """Converte a mensagem crua do SQLite em um erro de dominio."""
    texto = str(exc)

    unique = re.match(r"UNIQUE constraint failed: (.+)", texto)
    if unique:
        campo, mensagem = _MENSAGENS_UNIQUE.get(
            unique.group(1), ("_", "Registro duplicado.")
        )
        return Conflito(mensagem, {campo: mensagem})

    if "FOREIGN KEY constraint failed" in texto:
        return Conflito(
            "Operacao bloqueada: o registro esta vinculado a outros cadastros."
        )

    if "CHECK constraint failed" in texto or "NOT NULL constraint failed" in texto:
        return ValidacaoErro({"_": f"Restricao do banco violada ({texto})."})

    return ErroDominio(f"Erro de integridade: {texto}")
