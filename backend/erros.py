"""Excecoes de dominio compartilhadas pelo painel, pela API e pelos links."""

from __future__ import annotations

import logging
import re
import sqlite3

log = logging.getLogger(__name__)


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
        """Lista legivel para exibir no painel (flash), com o nome do campo como na tela
        ("Ano de início: ...", e não "ano_inicio: ...")."""
        if not self.campos:
            return [self.mensagem]
        return [texto if campo == "_" else f"{rotulo_campo(campo)}: {texto}" for campo, texto in self.campos.items()]


ROTULOS_CAMPOS = {
    "titulo": "Título", "nome": "Nome", "funcao": "Função", "email": "E-mail", "descricao": "Descrição",
    "categoria_id": "Categoria", "github_url": "GitHub", "lattes_url": "Lattes", "tags": "Tags",
    "foto": "Foto", "ativo": "Exibir na página", "modalidade": "Modalidade", "status": "Situação",
    "ano_inicio": "Ano de início", "ano_fim": "Ano de término", "orientador_id": "Orientador",
    "participantes": "Estudantes e colaboradores", "ano": "Ano", "tipo": "Tipo",
    "veiculo": "Revista / evento / editora", "autores": "Autores", "doi": "DOI", "url": "Link para leitura",
    "projeto_id": "Projeto", "valor": "Valor", "subtitulo": "Subtítulo", "link": "Link", "icone": "Ícone",
    "slug": "Identificador (gerado a partir do título)", "mensagem_vazia": "Mensagem sem membros",
    "ordem_exibicao": "Ordem de exibição", "imagem": "Imagem", "logo": "Logotipo",
    "texto_alternativo": "Descrição da imagem", "validade_dias": "Validade do link", "item_id": "Item",
    "recurso": "Tipo de cadastro", "acao": "Ação", "senha": "Senha", "confirmacao": "Confirmação da senha",
    "nova_senha": "Nova senha", "senha_atual": "Senha atual", "perfil": "Perfil",
    "nome_remetente": "Nome", "email_remetente": "E-mail", "assunto": "Assunto", "mensagem": "Mensagem",
    "hero_title": "Título principal", "hero_subtitle": "Subtítulo principal",
    "about_title": "Título da seção Sobre", "about_lead": "Frase de destaque (Sobre)",
    "about_description": "Descrição (Sobre)", "about_primary_button_text": "Botão principal - texto",
    "about_primary_button_link": "Botão principal - link", "about_secondary_button_text": "Botão secundário - texto",
    "about_secondary_button_link": "Botão secundário - link", "partners_title": "Título dos parceiros",
    "projects_page_title": "Projetos - título", "projects_page_subtitle": "Projetos - subtítulo",
    "projects_section_title": "Projetos - título da seção", "publications_page_title": "Publicações - título",
    "publications_page_subtitle": "Publicações - subtítulo", "publications_section_title": "Publicações - título da seção",
    "team_page_title": "Equipe - título", "team_page_subtitle": "Equipe - subtítulo",
}


def rotulo_campo(campo: str) -> str:
    return ROTULOS_CAMPOS.get(campo) or campo.replace("_", " ").capitalize()


class ValidacaoErro(ErroDominio):
    """Dados que violam regras de negocio (HTTP 422)."""

    status_http = 422

    def __init__(self, campos: dict[str, str], mensagem: str = "Dados inválidos."):
        super().__init__(mensagem, campos)


class NaoEncontrado(ErroDominio):
    status_http = 404


class Conflito(ErroDominio):
    """Violacao de unicidade ou registro em uso por outro (HTTP 409)."""

    status_http = 409


# Mensagens amigaveis para as restricoes UNIQUE do schema.
_MENSAGENS_UNIQUE = {
    "usuario.email": ("email", "Já existe um usuário com este e-mail."),
    "categoria_membro.slug": ("slug", "Já existe uma categoria com este identificador."),
    "categoria_membro.titulo": ("titulo", "Já existe uma categoria com este título."),
    "membro.email": ("email", "Já existe um membro com este e-mail."),
    "projeto.titulo": ("titulo", "Já existe um projeto com este título."),
    "projeto_participante.projeto_id, projeto_participante.membro_id": (
        "participantes",
        "O mesmo membro foi informado mais de uma vez.",
    ),
    "projeto_participante.projeto_id, projeto_participante.nome_externo": (
        "participantes",
        "O mesmo participante foi informado mais de uma vez.",
    ),
    "publicacao.doi": ("doi", "Já existe uma publicação com este DOI."),
    "publicacao.titulo, publicacao.ano": (
        "titulo",
        "Já existe uma publicação com este título neste ano.",
    ),
    "publicacao_autor.publicacao_id, publicacao_autor.membro_id": (
        "autores",
        "O mesmo membro foi informado mais de uma vez como autor.",
    ),
    "contato.tipo, contato.valor": ("valor", "Este canal de contato já está cadastrado."),
    "parceiro.nome": ("nome", "Já existe um parceiro com este nome."),
    "slider_imagem.imagem": ("imagem", "Esta imagem já está no slider."),
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
            "Operação bloqueada: o registro está vinculado a outros cadastros."
        )

    # O texto cru do SQLite revela nomes de tabelas e colunas: fica só no log do servidor.
    log.warning("restrição do banco violada: %s", texto)
    if "CHECK constraint failed" in texto or "NOT NULL constraint failed" in texto:
        return ValidacaoErro({"_": "Algum dado enviado não é aceito. Revise os campos e tente novamente."})

    return ErroDominio("Não foi possível salvar os dados. Revise os campos e tente novamente.")


class LimiteExcedido(ErroDominio):
    """Muitas requisições do mesmo endereço em pouco tempo (HTTP 429)."""

    status_http = 429
