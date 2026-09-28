"""Autenticacao do painel administrativo e da API.

* Painel: login pelo Firebase no navegador; o ID token (cookie) e validado
  uma vez e a identidade fica numa sessao Flask de 8 horas. Assim o admin
  nao perde um formulario quando o ID token (validade de 1 hora) expira.
* API: aceita a mesma sessao do painel ou o cabecalho
  `Authorization: Bearer <API_TOKEN>` (variavel de ambiente), usado para
  testes com Postman/Insomnia/curl.
"""

from __future__ import annotations

import hmac
import json
import os
import time
from functools import wraps
from pathlib import Path

from flask import flash, g, jsonify, redirect, request, session, url_for

from backend import repositorio as repo
from backend.contexto import get_db

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except ImportError:  # pragma: no cover - pacote pode faltar antes do setup
    firebase_admin = None
    firebase_auth = None
    credentials = None

BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_AUTH_COOKIE_NAME = "firebase_id_token"
CHAVE_SESSAO = "admin"
DURACAO_SESSAO = 8 * 60 * 60
EMAIL_USUARIO_API = "api@gptcode.local"
FIREBASE_CLIENT_REQUIRED_FIELDS = ("apiKey", "authDomain", "projectId", "messagingSenderId", "appId")


# ---------------------------------------------------------------------------
# Configuracao do Firebase
# ---------------------------------------------------------------------------

def resolve_env_path(variable_name: str) -> Path | None:
    raw_path = (os.getenv(variable_name) or "").strip()
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate
    return candidate.resolve()


def get_firebase_client_config() -> dict[str, str]:
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", "").strip(),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", "").strip(),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", "").strip(),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", "").strip(),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip(),
        "appId": os.getenv("FIREBASE_APP_ID", "").strip(),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", "").strip(),
    }


def is_firebase_client_configured() -> bool:
    config = get_firebase_client_config()
    return all(config.get(field) for field in FIREBASE_CLIENT_REQUIRED_FIELDS)


def get_firebase_service_account_path() -> Path | None:
    return resolve_env_path("FIREBASE_SERVICE_ACCOUNT_PATH") or resolve_env_path(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )


def get_firebase_service_account_dict() -> dict | None:
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def get_admin_allowed_emails() -> set[str]:
    raw_value = os.getenv("ADMIN_ALLOWED_EMAILS", "")
    return {item.strip().lower() for item in raw_value.split(",") if item.strip()}


def get_admin_allowed_domains() -> set[str]:
    raw_value = os.getenv("ADMIN_ALLOWED_DOMAINS", "")
    return {item.strip().lower() for item in raw_value.split(",") if item.strip()}


def is_admin_email_allowed(email: str) -> bool:
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        return False
    if normalized_email in get_admin_allowed_emails():
        return True
    domain = normalized_email.rsplit("@", 1)[1]
    return domain in get_admin_allowed_domains()


def get_firebase_setup_issues() -> list[str]:
    issues = []
    if firebase_admin is None or firebase_auth is None or credentials is None:
        issues.append("Instale a dependencia Python `firebase-admin` no ambiente.")
    if not is_firebase_client_configured():
        issues.append("Configure as variaveis `FIREBASE_*` do app web no servidor.")
    if get_firebase_service_account_path() is None and get_firebase_service_account_dict() is None:
        issues.append(
            "Defina `FIREBASE_SERVICE_ACCOUNT_JSON` (conteudo JSON) ou "
            "`FIREBASE_SERVICE_ACCOUNT_PATH` (caminho do arquivo) para o Firebase Admin SDK."
        )
    if not (get_admin_allowed_emails() or get_admin_allowed_domains()):
        issues.append("Defina `ADMIN_ALLOWED_EMAILS` ou `ADMIN_ALLOWED_DOMAINS` para limitar o acesso ao admin.")
    return issues


def ensure_firebase_admin_app():
    if firebase_admin is None or firebase_auth is None or credentials is None:
        raise RuntimeError("O suporte ao Firebase nao esta instalado no servidor.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        client_config = get_firebase_client_config()
        options = {"projectId": client_config["projectId"]} if client_config.get("projectId") else None

        service_account_dict = get_firebase_service_account_dict()
        if service_account_dict:
            return firebase_admin.initialize_app(credentials.Certificate(service_account_dict), options=options)

        credential_path = get_firebase_service_account_path()
        if credential_path:
            if not credential_path.exists():
                raise FileNotFoundError(f"Arquivo de credencial do Firebase nao encontrado em: {credential_path}")
            return firebase_admin.initialize_app(credentials.Certificate(str(credential_path)), options=options)

        return firebase_admin.initialize_app(options=options)


def get_admin_user_from_id_token(id_token: str) -> dict:
    ensure_firebase_admin_app()
    decoded_token = firebase_auth.verify_id_token(id_token)
    email = (decoded_token.get("email") or "").strip().lower()
    if not email:
        raise PermissionError("A conta autenticada nao possui email disponivel.")
    if not is_admin_email_allowed(email):
        raise PermissionError("Esta conta nao esta autorizada para acessar o painel administrativo.")
    return {"email": email, "name": (decoded_token.get("name") or "").strip() or email}


# ---------------------------------------------------------------------------
# Resolucao do usuario da requisicao
# ---------------------------------------------------------------------------

def _token_bearer() -> str | None:
    cabecalho = request.headers.get("Authorization", "")
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[7:].strip()
    return None


def _token_api_valido(token: str) -> bool:
    esperado = os.getenv("API_TOKEN", "").strip()
    return bool(esperado) and hmac.compare_digest(token.encode(), esperado.encode())


def encerrar_sessao() -> None:
    session.pop(CHAVE_SESSAO, None)


def carregar_usuario() -> None:
    """before_request: preenche g.admin_user nas rotas /admin e /api."""
    g.admin_user = None
    g.admin_auth_error = None
    if not request.path.startswith(("/admin", "/api")):
        return

    token = _token_bearer()
    if token is not None and request.path.startswith("/api"):
        if _token_api_valido(token):
            usuario = repo.registrar_acesso_usuario(get_db(), EMAIL_USUARIO_API, "Token da API", perfil="api")
            g.admin_user = {"email": usuario["email"], "name": usuario["nome"], "usuario_id": usuario["id"]}
        else:
            g.admin_auth_error = "Token da API invalido."
        return

    sessao = session.get(CHAVE_SESSAO)
    if sessao and sessao.get("expira_em", 0) > time.time():
        g.admin_user = sessao
        return
    encerrar_sessao()

    id_token = (request.cookies.get(ADMIN_AUTH_COOKIE_NAME) or "").strip()
    if not id_token:
        return
    try:
        dados = get_admin_user_from_id_token(id_token)
        usuario = repo.registrar_acesso_usuario(get_db(), dados["email"], dados["name"])
        if not usuario["ativo"]:
            raise PermissionError("Este usuario foi desativado.")
    except PermissionError as exc:
        g.admin_auth_error = str(exc)
        return
    except (FileNotFoundError, RuntimeError) as exc:
        g.admin_auth_error = str(exc)
        return
    except Exception:
        g.admin_auth_error = "Nao foi possivel validar o acesso pelo Firebase."
        return

    g.admin_user = {
        "email": usuario["email"],
        "name": usuario["nome"],
        "usuario_id": usuario["id"],
        "expira_em": time.time() + DURACAO_SESSAO,
    }
    session[CHAVE_SESSAO] = g.admin_user
    session.permanent = True


# ---------------------------------------------------------------------------
# Decoradores
# ---------------------------------------------------------------------------

def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if getattr(g, "admin_user", None):
            return view_function(*args, **kwargs)
        flash(getattr(g, "admin_auth_error", None) or "Faca login para acessar o painel administrativo.", "warning")
        response = redirect(url_for("admin_login"))
        if request.cookies.get(ADMIN_AUTH_COOKIE_NAME):
            response.delete_cookie(ADMIN_AUTH_COOKIE_NAME, path="/")
        return response

    return wrapped_view


def api_auth_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if getattr(g, "admin_user", None):
            return view_function(*args, **kwargs)
        mensagem = getattr(g, "admin_auth_error", None) or (
            "Autenticacao necessaria: envie 'Authorization: Bearer <API_TOKEN>' "
            "ou faca login no painel administrativo."
        )
        response = jsonify({"erro": mensagem})
        response.status_code = 401
        response.headers["WWW-Authenticate"] = 'Bearer realm="gptcode-api"'
        return response

    return wrapped_view
