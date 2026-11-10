"""Autenticação do painel (login pelo Firebase) e da API.

* Painel: o login é feito pelo Firebase Authentication no navegador. O ID token
  (cookie `firebase_id_token`) é conferido pelo servidor com o Firebase Admin SDK e só
  entram e-mails liberados em ADMIN_ALLOWED_EMAILS / ADMIN_ALLOWED_DOMAINS. A identidade
  então fica numa sessão Flask de 8 horas (o ID token do Firebase vale só 1 hora, e o
  painel não pode perder um formulário quando ele vence).
* CSRF: todo POST do painel precisa do campo oculto csrf_token, gerado por sessão
  (formulários) ou do cabeçalho X-CSRFToken (chamadas JSON).
* "Sair" invalida no servidor as sessões da conta (um cookie copiado deixa de valer).
* API: aceita a sessão do painel ou `Authorization: Bearer <API_TOKEN>` (variável de
  ambiente), usado para testes com Postman/Insomnia/curl.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import time
from functools import wraps
from pathlib import Path

from flask import abort, flash, g, jsonify, redirect, request, session, url_for
from markupsafe import Markup

from backend import repositorio as repo
from backend.contexto import get_db
from backend.erros import NaoEncontrado

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except ImportError:  # pragma: no cover - pacote pode faltar antes do setup
    firebase_admin = None
    firebase_auth = None
    credentials = None

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIE_FIREBASE = "firebase_id_token"
DURACAO_SESSAO = 8 * 60 * 60
CHAVE_USUARIO = "usuario_id"
CHAVE_CSRF = "csrf_token"
METODOS_ESCRITA = ("POST", "PUT", "PATCH", "DELETE")
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
# Sessão
# ---------------------------------------------------------------------------

def iniciar_sessao(usuario: dict) -> None:
    """Chamado após o login: nova sessão (evita fixação de sessão) e novo token CSRF."""
    session.clear()
    session.permanent = True
    session[CHAVE_USUARIO] = usuario["id"]
    # nunca antes do último "Sair" (ver sair()), senão a sessão nova nasceria inválida
    session["inicio"] = max(time.time(), usuario.get("sessoes_validas_desde") or 0)
    session[CHAVE_CSRF] = secrets.token_urlsafe(32)


def encerrar_sessao() -> None:
    session.clear()


def sair() -> None:
    """Logout: além de limpar o cookie, invalida no servidor as sessões desta conta
    (um cookie copiado antes do "Sair" deixa de funcionar)."""
    usuario = getattr(g, "usuario", None)
    if usuario and not g.via_token:
        # o relógio do Windows anda de 15 em 15 ms: garante o marco depois do início desta sessão
        desde = max(time.time(), session.get("inicio", 0)) + 0.001
        repo.encerrar_sessoes(get_db(), usuario["id"], desde)
    encerrar_sessao()


def csrf_token() -> str:
    if CHAVE_CSRF not in session:
        session[CHAVE_CSRF] = secrets.token_urlsafe(32)
    return session[CHAVE_CSRF]


def csrf_campo() -> Markup:
    """Campo oculto para os formulários do painel: {{ csrf_campo() }}."""
    return Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}" />')


def _token_bearer() -> str | None:
    cabecalho = request.headers.get("Authorization", "")
    if cabecalho.lower().startswith("bearer "):
        return cabecalho[7:].strip()
    return None


def _token_api_valido(token: str) -> bool:
    esperado = os.getenv("API_TOKEN", "").strip()
    return bool(esperado) and hmac.compare_digest(token.encode(), esperado.encode())


def _usuario_da_sessao() -> dict | None:
    usuario_id = session.get(CHAVE_USUARIO)
    if not usuario_id:
        return None
    if time.time() - session.get("inicio", 0) > DURACAO_SESSAO:
        g.erro_login = "Sua sessão expirou. Entre novamente."
        encerrar_sessao()
        return None
    try:
        usuario = repo.obter_usuario(get_db(), usuario_id)
    except NaoEncontrado:
        encerrar_sessao()
        return None
    if not usuario["ativo"] or usuario["perfil"] == "api":
        g.erro_login = "Esta conta foi desativada."
        encerrar_sessao()
        return None
    if session.get("inicio", 0) < usuario["sessoes_validas_desde"]:
        g.erro_login = "Sua sessão foi encerrada. Entre novamente."
        encerrar_sessao()
        return None
    return usuario


def _entrar_pelo_firebase() -> dict | None:
    """Sem sessão, mas com o cookie do Firebase: confere o ID token e abre a sessão."""
    id_token = (request.cookies.get(COOKIE_FIREBASE) or "").strip()
    if not id_token:
        return None
    try:
        dados = get_admin_user_from_id_token(id_token)
        usuario = repo.registrar_acesso_usuario(get_db(), dados["email"], dados["name"])
        if not usuario["ativo"]:
            raise PermissionError("Este usuário foi desativado.")
    except (PermissionError, FileNotFoundError, RuntimeError) as exc:
        g.erro_login = str(exc)
        return None
    except Exception:
        g.erro_login = "Não foi possível validar o acesso pelo Firebase."
        return None
    iniciar_sessao(usuario)
    return usuario


def carregar_usuario() -> None:
    """before_request: identifica o usuário nas rotas /admin e /api e confere o CSRF."""
    g.usuario = None
    g.erro_login = None
    g.via_token = False
    if not request.path.startswith(("/admin", "/api")):
        return

    token = _token_bearer()
    if token is not None and request.path.startswith("/api"):
        if _token_api_valido(token):
            g.usuario = repo.usuario_api(get_db())
            g.via_token = True
        else:
            g.erro_login = "Token da API inválido."
        return

    g.usuario = _usuario_da_sessao() or _entrar_pelo_firebase()

    if request.method in METODOS_ESCRITA and _exige_csrf():
        if request.path.startswith("/api"):
            conferir_csrf("Token CSRF ausente ou inválido. Envie o cabeçalho X-CSRFToken.")
        else:
            conferir_csrf()


def csrf_valido() -> bool:
    enviado = request.form.get(CHAVE_CSRF) or request.headers.get("X-CSRFToken", "")
    esperado = session.get(CHAVE_CSRF, "")
    return bool(esperado) and hmac.compare_digest(enviado.encode(), esperado.encode())


def conferir_csrf(mensagem: str = "Formulário expirado. Recarregue a página e tente novamente.") -> None:
    if not csrf_valido():
        abort(400, description=mensagem)


def _exige_csrf() -> bool:
    if request.path.startswith("/admin"):
        return True
    # API autenticada pela sessão do navegador (rotas públicas e token Bearer não usam CSRF)
    return request.path.startswith("/api") and bool(g.usuario) and not g.via_token


# ---------------------------------------------------------------------------
# Decoradores
# ---------------------------------------------------------------------------

def login_required(view_function):
    """Exige login no painel: qualquer conta ativa liberada no Firebase."""
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if getattr(g, "usuario", None):
            return view_function(*args, **kwargs)
        flash(getattr(g, "erro_login", None) or "Faça login para acessar o painel administrativo.", "warning")
        resposta = redirect(url_for("admin_login", proximo=request.full_path if request.method == "GET" else None))
        if request.cookies.get(COOKIE_FIREBASE):
            resposta.delete_cookie(COOKIE_FIREBASE, path="/")  # token recusado: não insiste nele
        return resposta

    return wrapped_view


def somente_admin_required(view_function):
    """Somente administradores."""
    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):
        if g.usuario.get("perfil") != "admin":
            abort(403, description="Somente administradores podem acessar esta página.")
        return view_function(*args, **kwargs)

    return wrapped_view


def api_auth_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if getattr(g, "usuario", None):
            return view_function(*args, **kwargs)
        mensagem = getattr(g, "erro_login", None) or (
            "Autenticação necessária: envie 'Authorization: Bearer <API_TOKEN>' "
            "ou faça login no painel administrativo."
        )
        resposta = jsonify({"erro": mensagem})
        resposta.status_code = 401
        resposta.headers["WWW-Authenticate"] = 'Bearer realm="gptcode-api"'
        return resposta

    return wrapped_view


def api_somente_admin_required(view_function):
    """API: somente administradores."""
    @wraps(view_function)
    @api_auth_required
    def wrapped_view(*args, **kwargs):
        if g.usuario.get("perfil") != "admin":
            return jsonify({"erro": "Somente administradores podem acessar este recurso."}), 403
        return view_function(*args, **kwargs)

    return wrapped_view


def proximo_seguro(destino: str | None) -> str | None:
    """Só aceita redirecionar para páginas do próprio painel (evita open redirect).
    Caracteres de controle (quebra de linha etc.) são recusados."""
    if not destino or any(ord(c) < 32 or ord(c) == 127 for c in destino):
        return None
    if destino.startswith("/admin") and not destino.startswith("//") and "\\" not in destino:
        return destino.rstrip("?")
    return None
