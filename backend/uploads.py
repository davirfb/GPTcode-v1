"""Upload de imagens para frontend/static/uploads/<pasta>/<uuid>.<ext>."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from backend.erros import ErroDominio, ValidacaoErro

STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
EXTENSOES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _tipo_real(cabecalho: bytes) -> str | None:
    """Extensão correspondente à assinatura (primeiros bytes) do arquivo, ou None.
    Não confia no nome: um .txt renomeado para .png é recusado."""
    if cabecalho.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if cabecalho.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if cabecalho.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return ".webp"
    return None


def salvar_imagem(arquivo, pasta: str, campo: str = "imagem") -> str | None:
    """Salva o upload e retorna o caminho relativo a /static, ou None se nao houver arquivo."""
    if not arquivo or not arquivo.filename:
        return None
    extensao = Path(secure_filename(arquivo.filename)).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValidacaoErro({campo: "Formato de imagem inválido. Use PNG, JPG, JPEG, GIF ou WEBP."})
    cabecalho = arquivo.stream.read(12)
    arquivo.stream.seek(0)
    tipo = _tipo_real(cabecalho)
    if tipo is None:
        raise ValidacaoErro({campo: "O arquivo enviado não é uma imagem válida (PNG, JPG, GIF ou WEBP)."})
    destino = UPLOADS_DIR / pasta
    destino.mkdir(parents=True, exist_ok=True)
    # a extensão gravada é a do conteúdo real (o navegador recebe o tipo certo)
    novo_nome = f"{uuid4().hex}{tipo}"
    arquivo.save(destino / novo_nome)
    return f"uploads/{pasta}/{novo_nome}"


def com_imagem(arquivo, pasta: str, campo: str, acao, obrigatoria: bool = False, mensagem_obrigatoria: str = ""):
    """Salva o upload, executa `acao(imagem)` e, se a ação falhar, apaga o arquivo
    recém-salvo (não deixa arquivo órfão). Se a ação devolver o caminho de uma
    imagem antiga substituída, ela é apagada depois do sucesso.

    `acao` pode devolver o caminho antigo (str), None, ou uma tupla
    (resultado, caminho_antigo); retorna o que a ação devolveu."""
    imagem = salvar_imagem(arquivo, pasta, campo)
    if obrigatoria and not imagem:
        raise ValidacaoErro({campo: mensagem_obrigatoria or "Selecione uma imagem."})
    try:
        retorno = acao(imagem)
    except ErroDominio:
        apagar_imagem(imagem)
        raise
    antiga = retorno[1] if isinstance(retorno, tuple) else retorno if isinstance(retorno, str) else None
    apagar_imagem(antiga)
    return retorno


def apagar_imagem(caminho: str | None) -> None:
    """Apaga apenas imagens enviadas pelo sistema (nunca as imagens fixas do site)."""
    if not caminho or not caminho.startswith("uploads/"):
        return
    arquivo = (STATIC_DIR / caminho).resolve()
    if UPLOADS_DIR.resolve() not in arquivo.parents:
        return
    arquivo.unlink(missing_ok=True)
