"""Aviso por e-mail aos administradores (Gmail SMTP).

Variáveis de ambiente:
  NOTIFICATION_EMAIL_FROM          endereço Gmail que envia
  NOTIFICATION_EMAIL_APP_PASSWORD  senha de app do Google (16 caracteres)

Sem essas variáveis, ou sem destinatários, nada é enviado.
"""

from __future__ import annotations

import logging
import os
import smtplib
import threading
from email.mime.text import MIMEText

log = logging.getLogger(__name__)
SEGUNDOS_LIMITE_SMTP = 10


def _configuracao() -> tuple[str, str]:
    return (
        os.getenv("NOTIFICATION_EMAIL_FROM", "").strip(),
        os.getenv("NOTIFICATION_EMAIL_APP_PASSWORD", "").strip(),
    )


def _enviar(remetente: str, senha: str, mensagem: MIMEText, destinatarios: list[str]) -> None:
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=SEGUNDOS_LIMITE_SMTP) as smtp:
            smtp.login(remetente, senha)
            smtp.sendmail(remetente, destinatarios, mensagem.as_string())
    except (OSError, smtplib.SMTPException):
        # o e-mail é só um aviso: a falha não pode derrubar o envio, mas precisa ficar registrada
        log.exception("não foi possível enviar o aviso por e-mail para %s", ", ".join(destinatarios))


def enviar_aviso(assunto: str, corpo: str, destinatarios: list[str]) -> None:
    """Envia o aviso em segundo plano: a pessoa não espera o SMTP para ver a resposta."""
    remetente, senha = _configuracao()
    if not remetente or not senha or not destinatarios:
        return
    mensagem = MIMEText(corpo, "plain", "utf-8")
    mensagem["Subject"] = f"[GPTCode] {assunto}"
    mensagem["From"] = remetente
    mensagem["To"] = ", ".join(destinatarios)
    threading.Thread(target=_enviar, args=(remetente, senha, mensagem, destinatarios), daemon=True).start()
