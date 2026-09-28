"""Regras de negocio de cada entidade.

Cada funcao `validar_*` recebe os dados de entrada (JSON da API ou
formulario HTML ja convertido em dict) e devolve um dict normalizado com
os nomes das colunas do banco, ou levanta `ValidacaoErro` com a lista de
campos invalidos. As mesmas funcoes sao usadas pelo painel, pela API e
pelos links de submissao, entao a regra e unica em todo o sistema.

As restricoes CHECK do schema continuam valendo como ultima barreira.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any, Iterable

from backend.erros import ValidacaoErro

MODALIDADES = ("PIBIC", "PIBITI", "TCC", "EXTENSAO", "OUTRO")
MODALIDADE_ROTULO = {
    "PIBIC": "PIBIC",
    "PIBITI": "PIBITI",
    "TCC": "PTCC/TCC",
    "EXTENSAO": "Extensao",
    "OUTRO": "Outros Projetos",
}
_MODALIDADE_ALIAS = {
    "PTCC/TCC": "TCC",
    "PTCC": "TCC",
    "EXTENSAO": "EXTENSAO",
    "OUTROS": "OUTRO",
    "OUTROS PROJETOS": "OUTRO",
}
STATUS_PROJETO = ("em_andamento", "concluido", "suspenso")
STATUS_PROJETO_ROTULO = {
    "em_andamento": "Em andamento",
    "concluido": "Concluido",
    "suspenso": "Suspenso",
}
PAPEIS_PARTICIPANTE = ("estudante", "coorientador", "colaborador")
TIPOS_PUBLICACAO = (
    "artigo",
    "anais",
    "capitulo",
    "livro",
    "resumo",
    "dissertacao",
    "tese",
    "relatorio",
    "outro",
)
TIPO_PUBLICACAO_ROTULO = {
    "artigo": "Artigo em periodico",
    "anais": "Trabalho em anais",
    "capitulo": "Capitulo de livro",
    "livro": "Livro",
    "resumo": "Resumo",
    "dissertacao": "Dissertacao",
    "tese": "Tese",
    "relatorio": "Relatorio tecnico",
    "outro": "Outro",
}
TIPOS_CONTATO = ("email", "telefone", "endereco", "rede_social", "site", "outro")
TIPO_CONTATO_ROTULO = {
    "email": "E-mail",
    "telefone": "Telefone",
    "endereco": "Endereco",
    "rede_social": "Rede social",
    "site": "Site",
    "outro": "Outro",
}
ICONE_PADRAO_CONTATO = {
    "email": "bi-envelope-fill",
    "telefone": "bi-telephone-fill",
    "endereco": "bi-geo-alt-fill",
    "rede_social": "bi-share-fill",
    "site": "bi-globe",
    "outro": "bi-chat-dots-fill",
}
RECURSOS_LINK = ("projeto", "publicacao", "membro")
ACOES_LINK = ("criar", "editar")

# Chaves de configuracao que o painel/API podem alterar.
CHAVES_CONFIGURACAO = (
    "hero_title",
    "hero_subtitle",
    "about_title",
    "about_lead",
    "about_description",
    "about_primary_button_text",
    "about_primary_button_link",
    "about_secondary_button_text",
    "about_secondary_button_link",
    "partners_title",
    "projects_page_title",
    "projects_page_subtitle",
    "projects_section_title",
    "publications_page_title",
    "publications_page_subtitle",
    "publications_section_title",
    "team_page_title",
    "team_page_subtitle",
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_ICONE_RE = re.compile(r"^bi-[a-z0-9-]+$")
_GITHUB_USUARIO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_LATTES_ID_RE = re.compile(r"^\d{16}$")


# ---------------------------------------------------------------------------
# Utilitarios
# ---------------------------------------------------------------------------

def texto_ou_nulo(valor: Any) -> str | None:
    """Normaliza entrada textual: remove espacos e converte vazio em None."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        valor = "1" if valor else "0"
    texto = str(valor).strip()
    return texto or None


def normalizar_nome(nome: str) -> str:
    """Chave de comparacao de nomes: sem acento, sem titulos e sem 'de/da/dos'."""
    sem_acento = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    palavras = re.split(r"[\s.]+", sem_acento.lower())
    ignorar = {"", "prof", "profa", "dr", "dra", "me", "ma", "msc", "de", "da", "do", "dos", "das", "e"}
    return " ".join(p for p in palavras if p not in ignorar)


def slugificar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    base = "".join(c for c in base if not unicodedata.combining(c)).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    if not base or not base[0].isalpha():
        base = f"c-{base}".strip("-")
    return base[:60]


def dividir_lista(valor: Any, separadores: str = r"\n|;") -> list[Any]:
    """Aceita lista (API) ou texto com um item por linha (formulario)."""
    if valor is None:
        return []
    if isinstance(valor, (list, tuple)):
        return list(valor)
    return [parte for parte in re.split(separadores, str(valor)) if parte.strip()]


class _Leitor:
    """Acumula erros de varios campos para devolve-los de uma vez."""

    def __init__(self, dados: dict[str, Any] | None):
        self.dados = dados or {}
        self.erros: dict[str, str] = {}
        self.saida: dict[str, Any] = {}

    def falhar(self, campo: str, mensagem: str) -> None:
        self.erros.setdefault(campo, mensagem)

    def texto(
        self,
        campo: str,
        *,
        obrigatorio: bool = False,
        minimo: int = 0,
        maximo: int | None = None,
        padrao: str | None = None,
    ) -> str | None:
        valor = texto_ou_nulo(self.dados.get(campo))
        if valor is None:
            if obrigatorio:
                self.falhar(campo, "Campo obrigatorio.")
            self.saida[campo] = padrao
            return padrao
        if len(valor) < minimo:
            self.falhar(campo, f"Informe ao menos {minimo} caracteres.")
        if maximo is not None and len(valor) > maximo:
            self.falhar(campo, f"Maximo de {maximo} caracteres.")
        self.saida[campo] = valor
        return valor

    def inteiro(
        self,
        campo: str,
        *,
        obrigatorio: bool = False,
        minimo: int | None = None,
        maximo: int | None = None,
    ) -> int | None:
        bruto = self.dados.get(campo)
        if isinstance(bruto, bool):
            self.falhar(campo, "Informe um numero inteiro.")
            return None
        texto = texto_ou_nulo(bruto)
        if texto is None:
            if obrigatorio:
                self.falhar(campo, "Campo obrigatorio.")
            self.saida[campo] = None
            return None
        try:
            numero = int(texto)
        except ValueError:
            self.falhar(campo, "Informe um numero inteiro.")
            return None
        if minimo is not None and numero < minimo:
            self.falhar(campo, f"O valor minimo e {minimo}.")
        if maximo is not None and numero > maximo:
            self.falhar(campo, f"O valor maximo e {maximo}.")
        self.saida[campo] = numero
        return numero

    def escolha(
        self,
        campo: str,
        opcoes: Iterable[str],
        *,
        obrigatorio: bool = False,
        padrao: str | None = None,
        normalizar=None,
    ) -> str | None:
        opcoes = tuple(opcoes)
        valor = texto_ou_nulo(self.dados.get(campo))
        if valor is None:
            if obrigatorio and padrao is None:
                self.falhar(campo, "Campo obrigatorio.")
            self.saida[campo] = padrao
            return padrao
        if normalizar:
            valor = normalizar(valor)
        if valor not in opcoes:
            self.falhar(campo, f"Valor invalido. Use um de: {', '.join(opcoes)}.")
            return None
        self.saida[campo] = valor
        return valor

    def booleano(self, campo: str, *, padrao: bool) -> bool:
        bruto = self.dados.get(campo)
        if bruto is None or bruto == "":
            valor = padrao
        elif isinstance(bruto, bool):
            valor = bruto
        elif str(bruto).strip().lower() in ("1", "true", "on", "sim", "yes"):
            valor = True
        elif str(bruto).strip().lower() in ("0", "false", "off", "nao", "no"):
            valor = False
        else:
            self.falhar(campo, "Use verdadeiro ou falso.")
            valor = padrao
        self.saida[campo] = 1 if valor else 0
        return valor

    def email(self, campo: str, *, obrigatorio: bool = False) -> str | None:
        valor = self.texto(campo, obrigatorio=obrigatorio, maximo=254)
        if valor is not None:
            valor = valor.lower()
            if not _EMAIL_RE.match(valor):
                self.falhar(campo, "E-mail invalido.")
            self.saida[campo] = valor
        return valor

    def url(self, campo: str, *, prefixos=("http://", "https://"), maximo: int = 500) -> str | None:
        valor = self.texto(campo, maximo=maximo)
        if valor is not None and not valor.lower().startswith(tuple(prefixos)):
            self.falhar(campo, f"O endereco deve comecar com {' ou '.join(prefixos)}.")
        return valor

    def concluir(self) -> dict[str, Any]:
        if self.erros:
            raise ValidacaoErro(self.erros)
        return self.saida


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------

def validar_categoria(dados: dict) -> dict:
    leitor = _Leitor(dados)
    titulo = leitor.texto("titulo", obrigatorio=True, maximo=80)
    slug = texto_ou_nulo(dados.get("slug")) or (slugificar(titulo) if titulo else None)
    if slug is not None and not re.match(r"^[a-z][a-z0-9-]*$", slug):
        leitor.falhar("slug", "Use apenas letras minusculas, numeros e hifen, iniciando por letra.")
    leitor.saida["slug"] = slug
    leitor.texto("mensagem_vazia", maximo=120, padrao="Nenhum membro por enquanto")
    leitor.inteiro("ordem_exibicao", minimo=0)
    return leitor.concluir()


def _normalizar_github(valor: str | None) -> str | None:
    if valor is None:
        return None
    bruto = valor.strip().rstrip("/")
    if _GITHUB_USUARIO_RE.match(bruto):
        return f"https://github.com/{bruto}"
    bruto = re.sub(r"^(https?://)?(www\.)?github\.com/", "https://github.com/", bruto, flags=re.I)
    return bruto


def _normalizar_lattes(valor: str | None) -> str | None:
    if valor is None:
        return None
    bruto = valor.strip()
    if _LATTES_ID_RE.match(bruto):
        return f"http://lattes.cnpq.br/{bruto}"
    if bruto.lower().startswith("lattes.cnpq.br/"):
        return f"http://{bruto}"
    return bruto


def validar_tags(valor: Any) -> list[str]:
    tags: list[str] = []
    vistos: set[str] = set()
    for item in dividir_lista(valor, r"\n|;|,"):
        nome = texto_ou_nulo(item)
        if nome is None:
            continue
        if len(nome) > 40:
            raise ValidacaoErro({"tags": f"A tag '{nome[:20]}...' passa de 40 caracteres."})
        chave = nome.casefold()
        if chave not in vistos:
            vistos.add(chave)
            tags.append(nome)
    if len(tags) > 10:
        raise ValidacaoErro({"tags": "Informe no maximo 10 tags."})
    return tags


def validar_membro(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.inteiro("categoria_id", obrigatorio=True, minimo=1)
    leitor.texto("nome", obrigatorio=True, minimo=3, maximo=120)
    leitor.texto("funcao", maximo=80)
    leitor.email("email")
    leitor.texto("descricao", maximo=800)
    leitor.booleano("ativo", padrao=True)
    leitor.inteiro("ordem_exibicao", minimo=0)

    github = _normalizar_github(texto_ou_nulo(dados.get("github_url")))
    if github is not None and not re.match(r"^https://github\.com/[A-Za-z0-9-]+(/.*)?$", github):
        leitor.falhar("github_url", "Informe o usuario ou o endereco https://github.com/usuario.")
    leitor.saida["github_url"] = github

    lattes = _normalizar_lattes(texto_ou_nulo(dados.get("lattes_url")))
    if lattes is not None and not re.match(r"^https?://[^\s]*cnpq\.br/\S+$", lattes):
        leitor.falhar("lattes_url", "Informe o endereco do curriculo Lattes (http://lattes.cnpq.br/...).")
    leitor.saida["lattes_url"] = lattes

    try:
        leitor.saida["tags"] = validar_tags(dados.get("tags"))
    except ValidacaoErro as exc:
        leitor.erros.update(exc.campos)
    return leitor.concluir()


def _normalizar_modalidade(valor: str) -> str:
    chave = unicodedata.normalize("NFKD", valor)
    chave = "".join(c for c in chave if not unicodedata.combining(c)).upper().strip()
    return _MODALIDADE_ALIAS.get(chave, chave)


def validar_participantes(valor: Any, campo: str = "participantes") -> list[dict]:
    """Aceita texto (um nome por linha / 'A e B') ou lista de nomes/objetos."""
    if isinstance(valor, str):
        itens: list[Any] = dividir_lista(valor, r"\n|;|,|\s+e\s+")
    else:
        itens = dividir_lista(valor)
    participantes = []
    for posicao, item in enumerate(itens, start=1):
        if isinstance(item, dict):
            membro_id = item.get("membro_id")
            nome = texto_ou_nulo(item.get("nome"))
            papel = texto_ou_nulo(item.get("papel")) or "estudante"
        else:
            membro_id, nome, papel = None, texto_ou_nulo(item), "estudante"
            # formato de formulario: "Nome (coorientador)"
            marcado = re.match(r"^(.*?)\s*\((\w+)\)$", nome or "")
            if marcado and marcado.group(2).lower() in PAPEIS_PARTICIPANTE:
                nome, papel = marcado.group(1).strip(), marcado.group(2).lower()
        if membro_id is not None:
            try:
                membro_id = int(membro_id)
            except (TypeError, ValueError):
                raise ValidacaoErro({campo: f"Item {posicao}: membro_id deve ser inteiro."})
        if membro_id is None and (nome is None or len(nome) < 3):
            raise ValidacaoErro({campo: f"Item {posicao}: informe o nome (min. 3 letras) ou o membro_id."})
        if nome is not None and len(nome) > 120:
            raise ValidacaoErro({campo: f"Item {posicao}: nome muito longo."})
        if papel not in PAPEIS_PARTICIPANTE:
            raise ValidacaoErro({campo: f"Item {posicao}: papel deve ser um de {', '.join(PAPEIS_PARTICIPANTE)}."})
        participantes.append({"membro_id": membro_id, "nome": nome, "papel": papel})
    if len(participantes) > 20:
        raise ValidacaoErro({campo: "Informe no maximo 20 participantes."})
    return participantes


def validar_projeto(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.texto("titulo", obrigatorio=True, minimo=5, maximo=200)
    leitor.escolha("modalidade", MODALIDADES, obrigatorio=True, normalizar=_normalizar_modalidade)
    status = leitor.escolha("status", STATUS_PROJETO, padrao="em_andamento")
    inicio = leitor.inteiro("ano_inicio", minimo=2000, maximo=2100)
    fim = leitor.inteiro("ano_fim", minimo=2000, maximo=2100)
    leitor.texto("descricao", maximo=3000)
    leitor.inteiro("orientador_id", minimo=1)
    leitor.inteiro("ordem_exibicao", minimo=0)

    if fim is not None and inicio is None:
        leitor.falhar("ano_inicio", "Informe o ano de inicio quando houver ano de termino.")
    if fim is not None and inicio is not None and fim < inicio:
        leitor.falhar("ano_fim", "O ano de termino nao pode ser anterior ao de inicio.")
    if status == "concluido" and fim is None:
        leitor.falhar("ano_fim", "Projeto concluido precisa do ano de termino.")

    try:
        leitor.saida["participantes"] = validar_participantes(dados.get("participantes"))
    except ValidacaoErro as exc:
        leitor.erros.update(exc.campos)
    return leitor.concluir()


def normalizar_doi(valor: str | None) -> str | None:
    if valor is None:
        return None
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", valor.strip(), flags=re.I)
    return doi or None


def validar_autores(valor: Any) -> list[dict]:
    autores = []
    for posicao, item in enumerate(dividir_lista(valor), start=1):
        if isinstance(item, dict):
            nome = texto_ou_nulo(item.get("nome") or item.get("nome_citacao"))
            membro_id = item.get("membro_id")
        else:
            nome, membro_id = texto_ou_nulo(item), None
        if nome is None or len(nome) < 2:
            raise ValidacaoErro({"autores": f"Autor {posicao}: informe o nome como aparece na citacao."})
        if len(nome) > 150:
            raise ValidacaoErro({"autores": f"Autor {posicao}: nome muito longo."})
        if membro_id is not None:
            try:
                membro_id = int(membro_id)
            except (TypeError, ValueError):
                raise ValidacaoErro({"autores": f"Autor {posicao}: membro_id deve ser inteiro."})
        autores.append({"nome_citacao": nome, "membro_id": membro_id})
    if not autores:
        raise ValidacaoErro({"autores": "Informe ao menos um autor."})
    if len(autores) > 50:
        raise ValidacaoErro({"autores": "Informe no maximo 50 autores."})
    return autores


def validar_publicacao(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.texto("titulo", obrigatorio=True, minimo=5, maximo=300)
    leitor.inteiro("ano", obrigatorio=True, minimo=1950, maximo=date.today().year + 1)
    leitor.escolha("tipo", TIPOS_PUBLICACAO, padrao="artigo", normalizar=str.lower)
    leitor.texto("veiculo", maximo=300)
    leitor.url("url")
    leitor.inteiro("projeto_id", minimo=1)
    leitor.inteiro("ordem_exibicao", minimo=0)

    doi = normalizar_doi(texto_ou_nulo(dados.get("doi")))
    if doi is not None and not _DOI_RE.match(doi):
        leitor.falhar("doi", "DOI invalido. Exemplo: 10.1590/1234-5678.2024.001")
    leitor.saida["doi"] = doi

    try:
        leitor.saida["autores"] = validar_autores(dados.get("autores"))
    except ValidacaoErro as exc:
        leitor.erros.update(exc.campos)
    return leitor.concluir()


def validar_contato(dados: dict) -> dict:
    leitor = _Leitor(dados)
    tipo = leitor.escolha("tipo", TIPOS_CONTATO, obrigatorio=True, normalizar=str.lower)
    leitor.texto("titulo", obrigatorio=True, maximo=60)
    valor = leitor.texto("valor", obrigatorio=True, maximo=300)
    leitor.texto("subtitulo", maximo=120)
    leitor.inteiro("ordem_exibicao", minimo=0)

    if tipo == "email" and valor is not None:
        if not _EMAIL_RE.match(valor):
            leitor.falhar("valor", "Para contatos do tipo e-mail, informe um e-mail valido.")
        else:
            leitor.saida["valor"] = valor.lower()

    link = leitor.url("link", prefixos=("http://", "https://", "mailto:", "tel:"))
    if link is None and tipo == "email" and valor and _EMAIL_RE.match(valor):
        leitor.saida["link"] = f"mailto:{valor.lower()}"

    icone = texto_ou_nulo(dados.get("icone"))
    if icone is None:
        icone = ICONE_PADRAO_CONTATO.get(tipo or "outro", "bi-chat-dots-fill")
    elif not _ICONE_RE.match(icone):
        leitor.falhar("icone", "Use o nome de um icone do Bootstrap Icons (ex.: bi-envelope-fill).")
    leitor.saida["icone"] = icone
    return leitor.concluir()


def validar_mensagem(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.texto("nome_remetente", obrigatorio=True, minimo=2, maximo=120)
    leitor.email("email_remetente", obrigatorio=True)
    leitor.texto("assunto", maximo=150)
    leitor.texto("mensagem", obrigatorio=True, minimo=10, maximo=5000)
    return leitor.concluir()


def validar_parceiro(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.texto("nome", obrigatorio=True, maximo=120)
    leitor.url("link")
    leitor.inteiro("ordem_exibicao", minimo=0)
    return leitor.concluir()


def validar_slider(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.texto("texto_alternativo", obrigatorio=True, maximo=150)
    leitor.inteiro("ordem_exibicao", minimo=0)
    return leitor.concluir()


def validar_configuracoes(dados: dict) -> dict[str, str]:
    desconhecidas = [chave for chave in dados if chave not in CHAVES_CONFIGURACAO]
    if desconhecidas:
        raise ValidacaoErro({chave: "Chave de configuracao desconhecida." for chave in desconhecidas})
    leitor = _Leitor(dados)
    for chave in dados:
        valor = leitor.texto(chave, maximo=2000)
        if chave.endswith("_link") and valor and not valor.startswith(("/", "http://", "https://", "#")):
            leitor.falhar(chave, "Use um caminho interno (/equipe) ou um endereco http(s).")
    saida = leitor.concluir()
    return {chave: valor or "" for chave, valor in saida.items()}


def validar_destaque(dados: dict) -> dict:
    leitor = _Leitor(dados)
    tipo = leitor.escolha("tipo", ("projeto", "publicacao", "nenhum"), padrao="nenhum")
    item_id = leitor.inteiro("item_id", minimo=1)
    if tipo in ("projeto", "publicacao") and item_id is None:
        leitor.falhar("item_id", "Informe o item a destacar.")
    saida = leitor.concluir()
    return {
        "projeto_id": saida["item_id"] if tipo == "projeto" else None,
        "publicacao_id": saida["item_id"] if tipo == "publicacao" else None,
    }


def validar_link(dados: dict) -> dict:
    leitor = _Leitor(dados)
    leitor.escolha("recurso", RECURSOS_LINK, obrigatorio=True)
    acao = leitor.escolha("acao", ACOES_LINK, obrigatorio=True)
    item_id = leitor.inteiro("item_id", minimo=1)
    leitor.inteiro("validade_dias", minimo=1, maximo=30)
    if acao == "editar" and item_id is None:
        leitor.falhar("item_id", "Links de edicao precisam do item a editar.")
    if acao == "criar" and item_id is not None:
        leitor.falhar("item_id", "Links de criacao nao recebem item_id.")
    saida = leitor.concluir()
    saida["validade_dias"] = saida["validade_dias"] or 7
    return saida
