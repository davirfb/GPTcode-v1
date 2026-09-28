"""Upload de imagens para frontend/static/uploads/<pasta>/<uuid>.<ext>."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from backend.erros import ValidacaoErro

STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
EXTENSOES_PERMITIDAS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def salvar_imagem(arquivo, pasta: str, campo: str = "imagem") -> str | None:
    """Salva o upload e retorna o caminho relativo a /static, ou None se nao houver arquivo."""
    if not arquivo or not arquivo.filename:
        return None
    nome = secure_filename(arquivo.filename)
    extensao = Path(nome).suffix.lower()
    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValidacaoErro({campo: "Formato de imagem invalido. Use PNG, JPG, JPEG, GIF ou WEBP."})
    destino = UPLOADS_DIR / pasta
    destino.mkdir(parents=True, exist_ok=True)
    novo_nome = f"{uuid4().hex}{extensao}"
    arquivo.save(destino / novo_nome)
    return f"uploads/{pasta}/{novo_nome}"


def apagar_imagem(caminho: str | None) -> None:
    """Apaga apenas imagens enviadas pelo sistema (nunca as imagens fixas do site)."""
    if not caminho or not caminho.startswith("uploads/"):
        return
    arquivo = (STATIC_DIR / caminho).resolve()
    if UPLOADS_DIR.resolve() not in arquivo.parents:
        return
    arquivo.unlink(missing_ok=True)
