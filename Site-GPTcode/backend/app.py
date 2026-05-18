from __future__ import annotations

import json
import os
from functools import wraps
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except ImportError:  # pragma: no cover - package may be missing before setup
    firebase_admin = None
    firebase_auth = None
    credentials = None

try:
    from .content_manager import load_site_content, save_site_content
    from .token_manager import generate_token, validate_token, mark_token_used
    from .pending_manager import (
        add_pending,
        get_pending_list,
        get_pending_item,
        mark_approved,
        mark_rejected,
        count_pending,
    )
    from .mailer import send_notification
except ImportError:  # pragma: no cover - fallback for `python backend/app.py`
    from content_manager import load_site_content, save_site_content
    from token_manager import generate_token, validate_token, mark_token_used
    from pending_manager import (
        add_pending,
        get_pending_list,
        get_pending_item,
        mark_approved,
        mark_rejected,
        count_pending,
    )
    from mailer import send_notification


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
ADMIN_AUTH_COOKIE_NAME = "firebase_id_token"
FIREBASE_CLIENT_REQUIRED_FIELDS = (
    "apiKey",
    "authDomain",
    "projectId",
    "messagingSenderId",
    "appId",
)

app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR / "static"),
    template_folder=str(FRONTEND_DIR / "templates"),
)
app.config["ENV"] = "development"
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "gptcode-admin-dev-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if getattr(g, "admin_user", None):
            return view_function(*args, **kwargs)

        flash(
            getattr(g, "admin_auth_error", None)
            or "Faca login para acessar o painel administrativo.",
            "warning",
        )
        response = redirect(url_for("admin_login"))
        if request.cookies.get(ADMIN_AUTH_COOKIE_NAME):
            response.delete_cookie(ADMIN_AUTH_COOKIE_NAME, path="/")
        return response

    return wrapped_view


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


def get_admin_allowed_emails() -> set[str]:
    raw_value = os.getenv("ADMIN_ALLOWED_EMAILS", "")
    return {item.strip().lower() for item in raw_value.split(",") if item.strip()}


def get_admin_allowed_domains() -> set[str]:
    raw_value = os.getenv("ADMIN_ALLOWED_DOMAINS", "")
    return {item.strip().lower() for item in raw_value.split(",") if item.strip()}


def has_admin_access_rules() -> bool:
    return bool(get_admin_allowed_emails() or get_admin_allowed_domains())


def is_admin_email_allowed(email: str) -> bool:
    normalized_email = email.strip().lower()
    if not normalized_email:
        return False

    allowed_emails = get_admin_allowed_emails()
    if normalized_email in allowed_emails:
        return True

    if "@" not in normalized_email:
        return False

    domain = normalized_email.rsplit("@", 1)[1]
    return domain in get_admin_allowed_domains()


def get_firebase_service_account_dict() -> dict | None:
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def get_firebase_setup_issues() -> list[str]:
    issues = []

    if firebase_admin is None or firebase_auth is None or credentials is None:
        issues.append("Instale a dependencia Python `firebase-admin` no ambiente.")

    if not is_firebase_client_configured():
        issues.append("Configure as variaveis `FIREBASE_*` do app web no servidor.")

    has_creds = (
        get_firebase_service_account_path() is not None
        or get_firebase_service_account_dict() is not None
    )
    if not has_creds:
        issues.append(
            "Defina `FIREBASE_SERVICE_ACCOUNT_JSON` (conteudo JSON) ou "
            "`FIREBASE_SERVICE_ACCOUNT_PATH` (caminho do arquivo) para o Firebase Admin SDK."
        )

    if not has_admin_access_rules():
        issues.append(
            "Defina `ADMIN_ALLOWED_EMAILS` ou `ADMIN_ALLOWED_DOMAINS` para limitar o acesso ao admin."
        )

    return issues


def ensure_firebase_admin_app():
    if firebase_admin is None or firebase_auth is None or credentials is None:
        raise RuntimeError("O suporte ao Firebase nao esta instalado no servidor.")

    try:
        return firebase_admin.get_app()
    except ValueError:
        client_config = get_firebase_client_config()
        options = {}
        if client_config.get("projectId"):
            options["projectId"] = client_config["projectId"]

        service_account_dict = get_firebase_service_account_dict()
        if service_account_dict:
            return firebase_admin.initialize_app(
                credentials.Certificate(service_account_dict),
                options=options or None,
            )

        credential_path = get_firebase_service_account_path()
        if credential_path:
            if not credential_path.exists():
                raise FileNotFoundError(
                    f"Arquivo de credencial do Firebase nao encontrado em: {credential_path}"
                )

            return firebase_admin.initialize_app(
                credentials.Certificate(str(credential_path)),
                options=options or None,
            )

        return firebase_admin.initialize_app(options=options or None)


def clean_text(value: str | None) -> str:
    return (value or "").strip()


def get_admin_user_from_id_token(id_token: str) -> dict:
    ensure_firebase_admin_app()
    decoded_token = firebase_auth.verify_id_token(id_token)

    email = clean_text(decoded_token.get("email")).lower()
    if not email:
        raise PermissionError("A conta autenticada nao possui email disponivel.")

    if not is_admin_email_allowed(email):
        raise PermissionError(
            "Esta conta nao esta autorizada para acessar o painel administrativo."
        )

    return {
        "email": email,
        "name": clean_text(decoded_token.get("name")) or email,
        "uid": decoded_token.get("uid", ""),
    }


def parse_tags(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def is_allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def save_uploaded_image(file_storage, folder_name: str) -> str:
    if not file_storage or not file_storage.filename:
        return ""

    filename = secure_filename(file_storage.filename)
    if not filename or not is_allowed_image(filename):
        raise ValueError("Formato de imagem invalido. Use PNG, JPG, JPEG, GIF ou WEBP.")

    target_dir = UPLOADS_DIR / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    new_filename = f"{uuid4().hex}{Path(filename).suffix.lower()}"
    file_path = target_dir / new_filename
    file_storage.save(file_path)
    return f"uploads/{folder_name}/{new_filename}"


def delete_managed_image(image_path: str | None) -> None:
    if not image_path or not image_path.startswith("uploads/"):
        return

    file_path = (STATIC_DIR / image_path).resolve()
    static_dir = STATIC_DIR.resolve()
    if static_dir not in file_path.parents:
        return
    if file_path.exists():
        file_path.unlink()


def find_item(items: list[dict], item_id: str) -> dict | None:
    for item in items:
        if item.get("id") == item_id:
            return item
    return None


def build_team_sections(team_content: dict) -> list[dict]:
    members = team_content.get("members", [])
    sections = []
    for category in team_content.get("categories", []):
        category_members = [
            member for member in members if member.get("category") == category.get("id")
        ]
        sections.append(
            {
                "id": category.get("id"),
                "title": category.get("title"),
                "empty_message": category.get("empty_message"),
                "members": category_members,
            }
        )
    return sections


def build_admin_team_sections(team_content: dict) -> list[dict]:
    valid_category_ids = {cat["id"] for cat in team_content.get("categories", [])}
    members = team_content.get("members", [])
    sections = []
    for category in team_content.get("categories", []):
        category_members = [m for m in members if m.get("category") == category["id"]]
        sections.append(
            {
                "id": category["id"],
                "title": category["title"],
                "members": category_members,
            }
        )
    orphaned = [m for m in members if m.get("category", "") not in valid_category_ids]
    if orphaned:
        sections.append(
            {
                "id": "_sem_categoria",
                "title": "Sem categoria (ocultos no site)",
                "members": orphaned,
            }
        )
    return sections


def get_dashboard_stats(content: dict) -> dict:
    return {
        "slider_images": len(content["home"]["about"]["slider"]),
        "partners": len(content["home"]["partners"]),
        "projects": len(content["projects"]["items"]),
        "publications": len(content["publications"]["items"]),
        "team_members": len(content["team"]["members"]),
    }


@app.before_request
def load_admin_auth_state() -> None:
    g.admin_user = None
    g.admin_auth_error = None

    if not request.path.startswith("/admin"):
        return

    id_token = clean_text(request.cookies.get(ADMIN_AUTH_COOKIE_NAME))
    if not id_token:
        return

    try:
        g.admin_user = get_admin_user_from_id_token(id_token)
    except PermissionError as exc:
        g.admin_auth_error = str(exc)
    except (FileNotFoundError, RuntimeError) as exc:
        g.admin_auth_error = str(exc)
    except Exception:
        g.admin_auth_error = "Nao foi possivel validar o acesso pelo Firebase."


@app.context_processor
def inject_admin_state():
    firebase_setup_issues = get_firebase_setup_issues()
    return {
        "admin_logged_in": bool(getattr(g, "admin_user", None)),
        "firebase_config": get_firebase_client_config(),
        "firebase_ready": not firebase_setup_issues,
        "firebase_setup_issues": firebase_setup_issues,
        "pending_count": count_pending(),
    }


def resolve_highlight(content: dict) -> dict | None:
    ref = content["home"].get("highlight", {})
    item_type = ref.get("type", "none")
    item_id = ref.get("item_id", "")
    if item_type == "publication" and item_id:
        item = find_item(content["publications"]["items"], item_id)
        if item:
            return {"type": "publication", "item": item}
    elif item_type == "project" and item_id:
        item = find_item(content["projects"]["items"], item_id)
        if item:
            return {"type": "project", "item": item}
    return None


@app.route("/")
def index():
    content = load_site_content()
    return render_template("index.html", home=content["home"], highlight=resolve_highlight(content))


@app.route("/contato")
def contato():
    return render_template("contato.html")


@app.route("/equipe")
def equipe():
    content = load_site_content()
    team_content = content["team"]
    return render_template(
        "equipe.html",
        team=team_content,
        team_sections=build_team_sections(team_content),
    )


@app.route("/publicacoes")
def publicacoes():
    content = load_site_content()
    return render_template("publicacoes.html", publications=content["publications"])


@app.route("/projetos")
def projetos():
    content = load_site_content()
    return render_template("projetos.html", projects=content["projects"])


@app.route("/admin/login")
def admin_login():
    if getattr(g, "admin_user", None):
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("Sessao encerrada com sucesso.", "success")
    response = redirect(url_for("admin_login"))
    response.delete_cookie(ADMIN_AUTH_COOKIE_NAME, path="/")
    return response


@app.route("/admin")
@admin_required
def admin_dashboard():
    content = load_site_content()
    return render_template(
        "admin/dashboard.html",
        stats=get_dashboard_stats(content),
        home=content["home"],
        projects=content["projects"],
        publications=content["publications"],
        team=content["team"],
    )


@app.route("/admin/home")
@admin_required
def admin_home():
    content = load_site_content()
    return render_template(
        "admin/home.html",
        home=content["home"],
        projects=content["projects"],
        publications=content["publications"],
    )


@app.route("/admin/home/settings", methods=["POST"])
@admin_required
def admin_update_home_settings():
    content = load_site_content()
    home = content["home"]

    home["hero"]["title"] = clean_text(request.form.get("hero_title"))
    home["hero"]["subtitle"] = clean_text(request.form.get("hero_subtitle"))

    home["about"]["title"] = clean_text(request.form.get("about_title"))
    home["about"]["lead"] = clean_text(request.form.get("about_lead"))
    home["about"]["description"] = clean_text(request.form.get("about_description"))
    home["about"]["primary_button_text"] = clean_text(
        request.form.get("primary_button_text")
    )
    home["about"]["primary_button_link"] = clean_text(
        request.form.get("primary_button_link")
    )
    home["about"]["secondary_button_text"] = clean_text(
        request.form.get("secondary_button_text")
    )
    home["about"]["secondary_button_link"] = clean_text(
        request.form.get("secondary_button_link")
    )
    home["partners_title"] = clean_text(request.form.get("partners_title"))

    save_site_content(content)
    flash("Textos da pagina inicial atualizados.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/highlight", methods=["POST"])
@admin_required
def admin_update_highlight():
    content = load_site_content()
    selection = clean_text(request.form.get("highlight_selection", "none")) or "none"

    if ":" in selection:
        item_type, item_id = selection.split(":", 1)
        if item_type in ("project", "publication"):
            content["home"]["highlight"] = {"type": item_type, "item_id": item_id}
        else:
            content["home"]["highlight"] = {"type": "none", "item_id": ""}
    else:
        content["home"]["highlight"] = {"type": "none", "item_id": ""}

    save_site_content(content)
    flash("Destaque principal atualizado.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/slider/add", methods=["POST"])
@admin_required
def admin_add_slider_image():
    content = load_site_content()
    image_file = request.files.get("image")

    try:
        image_path = save_uploaded_image(image_file, "about-slider")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_home"))

    if not image_path:
        flash("Selecione uma imagem para adicionar ao slider.", "danger")
        return redirect(url_for("admin_home"))

    content["home"]["about"]["slider"].append(
        {
            "id": f"about-slide-{uuid4().hex}",
            "image": image_path,
            "alt": clean_text(request.form.get("alt")) or "Imagem do slider",
        }
    )
    save_site_content(content)
    flash("Imagem adicionada ao slider.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/slider/<item_id>/update", methods=["POST"])
@admin_required
def admin_update_slider_image(item_id: str):
    content = load_site_content()
    item = find_item(content["home"]["about"]["slider"], item_id)
    if not item:
        flash("Imagem do slider nao encontrada.", "danger")
        return redirect(url_for("admin_home"))

    item["alt"] = clean_text(request.form.get("alt"))

    image_file = request.files.get("image")
    try:
        new_image = save_uploaded_image(image_file, "about-slider")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_home"))

    if new_image:
        delete_managed_image(item.get("image"))
        item["image"] = new_image

    save_site_content(content)
    flash("Imagem do slider atualizada.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/slider/<item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_slider_image(item_id: str):
    content = load_site_content()
    slider_items = content["home"]["about"]["slider"]
    item = find_item(slider_items, item_id)
    if not item:
        flash("Imagem do slider nao encontrada.", "danger")
        return redirect(url_for("admin_home"))

    slider_items.remove(item)
    delete_managed_image(item.get("image"))
    save_site_content(content)
    flash("Imagem removida do slider.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/partners/add", methods=["POST"])
@admin_required
def admin_add_partner():
    content = load_site_content()
    image_file = request.files.get("image")

    try:
        image_path = save_uploaded_image(image_file, "partners")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_home"))

    if not image_path:
        flash("Selecione a imagem do parceiro ou apoiador.", "danger")
        return redirect(url_for("admin_home"))

    content["home"]["partners"].append(
        {
            "id": f"partner-{uuid4().hex}",
            "name": clean_text(request.form.get("name")),
            "link": clean_text(request.form.get("link")),
            "image": image_path,
        }
    )
    save_site_content(content)
    flash("Parceiro ou apoiador adicionado.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/partners/<item_id>/update", methods=["POST"])
@admin_required
def admin_update_partner(item_id: str):
    content = load_site_content()
    partner = find_item(content["home"]["partners"], item_id)
    if not partner:
        flash("Parceiro nao encontrado.", "danger")
        return redirect(url_for("admin_home"))

    partner["name"] = clean_text(request.form.get("name"))
    partner["link"] = clean_text(request.form.get("link"))

    image_file = request.files.get("image")
    try:
        new_image = save_uploaded_image(image_file, "partners")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_home"))

    if new_image:
        delete_managed_image(partner.get("image"))
        partner["image"] = new_image

    save_site_content(content)
    flash("Parceiro atualizado.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/home/partners/<item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_partner(item_id: str):
    content = load_site_content()
    partners = content["home"]["partners"]
    partner = find_item(partners, item_id)
    if not partner:
        flash("Parceiro nao encontrado.", "danger")
        return redirect(url_for("admin_home"))

    partners.remove(partner)
    delete_managed_image(partner.get("image"))
    save_site_content(content)
    flash("Parceiro removido.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/projects")
@admin_required
def admin_projects():
    content = load_site_content()
    return render_template("admin/projects.html", projects=content["projects"])


@app.route("/admin/projects/settings", methods=["POST"])
@admin_required
def admin_update_projects_settings():
    content = load_site_content()
    page = content["projects"]["page"]
    page["title"] = clean_text(request.form.get("title"))
    page["subtitle"] = clean_text(request.form.get("subtitle"))
    page["section_title"] = clean_text(request.form.get("section_title"))
    save_site_content(content)
    flash("Cabecalho da pagina de projetos atualizado.", "success")
    return redirect(url_for("admin_projects"))


@app.route("/admin/projects/add", methods=["POST"])
@admin_required
def admin_add_project():
    content = load_site_content()
    content["projects"]["items"].append(
        {
            "id": f"project-{uuid4().hex}",
            "badge": clean_text(request.form.get("badge")),
            "title": clean_text(request.form.get("title")),
            "students": clean_text(request.form.get("students")),
            "advisor": clean_text(request.form.get("advisor")),
            "image": "",
            "about_text": clean_text(request.form.get("about_text")),
        }
    )
    save_site_content(content)
    flash("Projeto adicionado com sucesso.", "success")
    return redirect(url_for("admin_projects"))


@app.route("/admin/projects/<item_id>/update", methods=["POST"])
@admin_required
def admin_update_project(item_id: str):
    content = load_site_content()
    project = find_item(content["projects"]["items"], item_id)
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("admin_projects"))

    project["badge"] = clean_text(request.form.get("badge"))
    project["title"] = clean_text(request.form.get("title"))
    project["students"] = clean_text(request.form.get("students"))
    project["advisor"] = clean_text(request.form.get("advisor"))
    project["about_text"] = clean_text(request.form.get("about_text"))

    save_site_content(content)
    flash("Projeto atualizado.", "success")
    return redirect(url_for("admin_projects"))


@app.route("/admin/projects/<item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_project(item_id: str):
    content = load_site_content()
    projects = content["projects"]["items"]
    project = find_item(projects, item_id)
    if not project:
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("admin_projects"))

    projects.remove(project)
    delete_managed_image(project.get("image"))
    save_site_content(content)
    flash("Projeto removido.", "success")
    return redirect(url_for("admin_projects"))


@app.route("/admin/publications")
@admin_required
def admin_publications():
    content = load_site_content()
    return render_template(
        "admin/publications.html",
        publications=content["publications"],
    )


@app.route("/admin/publications/settings", methods=["POST"])
@admin_required
def admin_update_publications_settings():
    content = load_site_content()
    page = content["publications"]["page"]
    page["title"] = clean_text(request.form.get("title"))
    page["subtitle"] = clean_text(request.form.get("subtitle"))
    page["section_title"] = clean_text(request.form.get("section_title"))
    save_site_content(content)
    flash("Cabecalho da pagina de publicacoes atualizado.", "success")
    return redirect(url_for("admin_publications"))


@app.route("/admin/publications/add", methods=["POST"])
@admin_required
def admin_add_publication():
    content = load_site_content()
    content["publications"]["items"].append(
        {
            "id": f"publication-{uuid4().hex}",
            "year": clean_text(request.form.get("year")),
            "title": clean_text(request.form.get("title")),
            "participants": clean_text(request.form.get("participants")),
            "journal": clean_text(request.form.get("journal")),
            "doi_url": clean_text(request.form.get("doi_url")),
        }
    )
    save_site_content(content)
    flash("Publicacao adicionada com sucesso.", "success")
    return redirect(url_for("admin_publications"))


@app.route("/admin/publications/<item_id>/update", methods=["POST"])
@admin_required
def admin_update_publication(item_id: str):
    content = load_site_content()
    publication = find_item(content["publications"]["items"], item_id)
    if not publication:
        flash("Publicacao nao encontrada.", "danger")
        return redirect(url_for("admin_publications"))

    publication["year"] = clean_text(request.form.get("year"))
    publication["title"] = clean_text(request.form.get("title"))
    publication["participants"] = clean_text(request.form.get("participants"))
    publication["journal"] = clean_text(request.form.get("journal"))
    publication["doi_url"] = clean_text(request.form.get("doi_url"))

    save_site_content(content)
    flash("Publicacao atualizada.", "success")
    return redirect(url_for("admin_publications"))


@app.route("/admin/publications/<item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_publication(item_id: str):
    content = load_site_content()
    publications = content["publications"]["items"]
    publication = find_item(publications, item_id)
    if not publication:
        flash("Publicacao nao encontrada.", "danger")
        return redirect(url_for("admin_publications"))

    publications.remove(publication)
    save_site_content(content)
    flash("Publicacao removida.", "success")
    return redirect(url_for("admin_publications"))


@app.route("/admin/team")
@admin_required
def admin_team():
    content = load_site_content()
    team_content = content["team"]
    return render_template(
        "admin/team.html",
        team=team_content,
        team_sections=build_admin_team_sections(team_content),
    )


@app.route("/admin/team/settings", methods=["POST"])
@admin_required
def admin_update_team_settings():
    content = load_site_content()
    page = content["team"]["page"]
    page["title"] = clean_text(request.form.get("title"))
    page["subtitle"] = clean_text(request.form.get("subtitle"))
    save_site_content(content)
    flash("Cabecalho da pagina de equipe atualizado.", "success")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/categories/<category_id>/delete", methods=["POST"])
@admin_required
def admin_delete_team_category(category_id: str):
    content = load_site_content()
    categories = content["team"]["categories"]
    category = find_item(categories, category_id)
    if not category:
        flash("Categoria nao encontrada.", "danger")
        return redirect(url_for("admin_team"))

    for member in content["team"]["members"]:
        if member.get("category") == category_id:
            member["category"] = ""

    categories.remove(category)
    save_site_content(content)
    flash("Categoria removida.", "success")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/categories/<category_id>/update", methods=["POST"])
@admin_required
def admin_update_team_category(category_id: str):
    content = load_site_content()
    category = find_item(content["team"]["categories"], category_id)
    if not category:
        flash("Categoria da equipe nao encontrada.", "danger")
        return redirect(url_for("admin_team"))

    category["title"] = clean_text(request.form.get("title"))
    save_site_content(content)
    flash("Categoria atualizada.", "success")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/members/add", methods=["POST"])
@admin_required
def admin_add_team_member():
    content = load_site_content()
    category = clean_text(request.form.get("category"))
    valid_categories = {item["id"] for item in content["team"]["categories"]}
    if category not in valid_categories:
        flash("Categoria invalida para o membro.", "danger")
        return redirect(url_for("admin_team"))

    image_file = request.files.get("image")
    try:
        image_path = save_uploaded_image(image_file, "team")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_team"))

    if not image_path:
        flash("Selecione uma imagem para o membro da equipe.", "danger")
        return redirect(url_for("admin_team"))

    content["team"]["members"].append(
        {
            "id": f"member-{uuid4().hex}",
            "category": category,
            "name": clean_text(request.form.get("name")),
            "role": clean_text(request.form.get("role")),
            "github_url": clean_text(request.form.get("github_url")),
            "lattes_url": clean_text(request.form.get("lattes_url")),
            "description": clean_text(request.form.get("description")),
            "tags": parse_tags(request.form.get("tags")),
            "image": image_path,
        }
    )
    save_site_content(content)
    flash("Membro adicionado com sucesso.", "success")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/members/<item_id>/update", methods=["POST"])
@admin_required
def admin_update_team_member(item_id: str):
    content = load_site_content()
    member = find_item(content["team"]["members"], item_id)
    if not member:
        flash("Membro nao encontrado.", "danger")
        return redirect(url_for("admin_team"))

    category = clean_text(request.form.get("category"))
    valid_categories = {item["id"] for item in content["team"]["categories"]}
    if category not in valid_categories:
        flash("Categoria invalida para o membro.", "danger")
        return redirect(url_for("admin_team"))

    member["category"] = category
    member["name"] = clean_text(request.form.get("name"))
    member["role"] = clean_text(request.form.get("role"))
    member["github_url"] = clean_text(request.form.get("github_url"))
    member["lattes_url"] = clean_text(request.form.get("lattes_url"))
    member["description"] = clean_text(request.form.get("description"))
    member["tags"] = parse_tags(request.form.get("tags"))

    image_file = request.files.get("image")
    try:
        new_image = save_uploaded_image(image_file, "team")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for("admin_team"))

    if new_image:
        delete_managed_image(member.get("image"))
        member["image"] = new_image

    save_site_content(content)
    flash("Membro atualizado com sucesso.", "success")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/members/<item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_team_member(item_id: str):
    content = load_site_content()
    members = content["team"]["members"]
    member = find_item(members, item_id)
    if not member:
        flash("Membro nao encontrado.", "danger")
        return redirect(url_for("admin_team"))

    members.remove(member)
    delete_managed_image(member.get("image"))
    save_site_content(content)
    flash("Membro removido com sucesso.", "success")
    return redirect(url_for("admin_team"))


# ─── GENERATE ONE-TIME LINKS (admin only) ────────────────────────────────────

def _make_link(token_type: str, resource: str, item_id: str | None = None) -> str:
    admin_user = getattr(g, "admin_user", {}) or {}
    token = generate_token(token_type, resource, item_id, created_by=admin_user.get("email", ""))
    if resource == "project":
        return url_for("submit_resource", resource="project", token=token, _external=True)
    if resource == "publication":
        return url_for("submit_resource", resource="publication", token=token, _external=True)
    return url_for("submit_resource", resource="member", token=token, _external=True)


@app.route("/admin/projects/generate-link", methods=["POST"])
@admin_required
def admin_generate_project_add_link():
    link = _make_link("add", "project")
    flash(link, "generated_link")
    return redirect(url_for("admin_projects"))


@app.route("/admin/projects/<item_id>/generate-edit-link", methods=["POST"])
@admin_required
def admin_generate_project_edit_link(item_id: str):
    content = load_site_content()
    if not find_item(content["projects"]["items"], item_id):
        flash("Projeto nao encontrado.", "danger")
        return redirect(url_for("admin_projects"))
    link = _make_link("edit", "project", item_id)
    flash(link, "generated_link")
    return redirect(url_for("admin_projects"))


@app.route("/admin/publications/generate-link", methods=["POST"])
@admin_required
def admin_generate_publication_add_link():
    link = _make_link("add", "publication")
    flash(link, "generated_link")
    return redirect(url_for("admin_publications"))


@app.route("/admin/publications/<item_id>/generate-edit-link", methods=["POST"])
@admin_required
def admin_generate_publication_edit_link(item_id: str):
    content = load_site_content()
    if not find_item(content["publications"]["items"], item_id):
        flash("Publicacao nao encontrada.", "danger")
        return redirect(url_for("admin_publications"))
    link = _make_link("edit", "publication", item_id)
    flash(link, "generated_link")
    return redirect(url_for("admin_publications"))


@app.route("/admin/team/members/generate-link", methods=["POST"])
@admin_required
def admin_generate_member_add_link():
    link = _make_link("add", "member")
    flash(link, "generated_link")
    return redirect(url_for("admin_team"))


@app.route("/admin/team/members/<item_id>/generate-edit-link", methods=["POST"])
@admin_required
def admin_generate_member_edit_link(item_id: str):
    content = load_site_content()
    if not find_item(content["team"]["members"], item_id):
        flash("Membro nao encontrado.", "danger")
        return redirect(url_for("admin_team"))
    link = _make_link("edit", "member", item_id)
    flash(link, "generated_link")
    return redirect(url_for("admin_team"))


# ─── PUBLIC SUBMISSION FORM ───────────────────────────────────────────────────

@app.route("/submit/<resource>/<token>", methods=["GET", "POST"])
def submit_resource(resource: str, token: str):
    if resource not in ("project", "publication", "member"):
        abort(404)

    token_data = validate_token(token)
    if not token_data:
        return render_template("submit/invalid.html"), 410

    content = load_site_content()
    existing = None
    if token_data["type"] == "edit" and token_data.get("item_id"):
        item_id = token_data["item_id"]
        if resource == "project":
            existing = find_item(content["projects"]["items"], item_id)
        elif resource == "publication":
            existing = find_item(content["publications"]["items"], item_id)
        elif resource == "member":
            existing = find_item(content["team"]["members"], item_id)

    if request.method == "POST":
        if resource == "project":
            data = {
                "badge": clean_text(request.form.get("badge")),
                "title": clean_text(request.form.get("title")),
                "students": clean_text(request.form.get("students")),
                "advisor": clean_text(request.form.get("advisor")),
                "about_text": clean_text(request.form.get("about_text")),
            }
        elif resource == "publication":
            data = {
                "year": clean_text(request.form.get("year")),
                "title": clean_text(request.form.get("title")),
                "participants": clean_text(request.form.get("participants")),
                "journal": clean_text(request.form.get("journal")),
                "doi_url": clean_text(request.form.get("doi_url")),
            }
        else:  # member
            image_file = request.files.get("image")
            pending_image = ""
            if image_file and image_file.filename:
                try:
                    pending_image = save_uploaded_image(image_file, "pending-team")
                except ValueError:
                    pending_image = ""
            data = {
                "category": clean_text(request.form.get("category")),
                "name": clean_text(request.form.get("name")),
                "role": clean_text(request.form.get("role")),
                "github_url": clean_text(request.form.get("github_url")),
                "lattes_url": clean_text(request.form.get("lattes_url")),
                "description": clean_text(request.form.get("description")),
                "tags": parse_tags(request.form.get("tags")),
                "image": pending_image,
            }

        mark_token_used(token)
        add_pending(
            resource=resource,
            submission_type=token_data["type"],
            data=data,
            item_id=token_data.get("item_id"),
        )

        # notify all admin emails
        recipients = list(get_admin_allowed_emails())
        action = "adicionado" if token_data["type"] == "add" else "editado"
        labels = {"project": "Projeto", "publication": "Publicação", "member": "Membro"}
        send_notification(
            subject=f"Nova submissão pendente: {labels.get(resource, resource)}",
            body=(
                f"Uma nova submissão aguarda validação no painel administrativo.\n\n"
                f"Tipo: {labels.get(resource, resource)} ({action})\n"
                f"Acesse: {url_for('admin_pending', _external=True)}"
            ),
            recipients=recipients,
        )

        return render_template("submit/success.html")

    template_map = {
        "project": "submit/project.html",
        "publication": "submit/publication.html",
        "member": "submit/member.html",
    }
    return render_template(
        template_map[resource],
        token_data=token_data,
        existing=existing,
        categories=content["team"].get("categories", []) if resource == "member" else [],
    )


# ─── ADMIN PENDING VALIDATION ─────────────────────────────────────────────────

@app.route("/admin/pending")
@admin_required
def admin_pending():
    return render_template("admin/pending.html", submissions=get_pending_list())


@app.route("/admin/pending/<submission_id>/approve", methods=["POST"])
@admin_required
def admin_approve_submission(submission_id: str):
    submission = get_pending_item(submission_id)
    if not submission or submission.get("status") != "pending":
        flash("Submissão não encontrada ou já processada.", "danger")
        return redirect(url_for("admin_pending"))

    content = load_site_content()
    resource = submission["resource"]
    sub_type = submission["type"]
    data = submission["data"]

    if resource == "project":
        if sub_type == "add":
            content["projects"]["items"].append({
                "id": f"project-{uuid4().hex}",
                "badge": data.get("badge", ""),
                "title": data.get("title", ""),
                "students": data.get("students", ""),
                "advisor": data.get("advisor", ""),
                "image": "",
                "about_text": data.get("about_text", ""),
            })
        else:
            project = find_item(content["projects"]["items"], submission.get("item_id", ""))
            if project:
                project.update({k: data[k] for k in ("badge", "title", "students", "advisor", "about_text") if k in data})

    elif resource == "publication":
        if sub_type == "add":
            content["publications"]["items"].append({
                "id": f"publication-{uuid4().hex}",
                "year": data.get("year", ""),
                "title": data.get("title", ""),
                "participants": data.get("participants", ""),
                "journal": data.get("journal", ""),
                "doi_url": data.get("doi_url", ""),
            })
        else:
            pub = find_item(content["publications"]["items"], submission.get("item_id", ""))
            if pub:
                pub.update({k: data[k] for k in ("year", "title", "participants", "journal", "doi_url") if k in data})

    elif resource == "member":
        valid_categories = {c["id"] for c in content["team"].get("categories", [])}
        if sub_type == "add":
            content["team"]["members"].append({
                "id": f"member-{uuid4().hex}",
                "category": data.get("category", "") if data.get("category") in valid_categories else "",
                "name": data.get("name", ""),
                "role": data.get("role", ""),
                "github_url": data.get("github_url", ""),
                "lattes_url": data.get("lattes_url", ""),
                "description": data.get("description", ""),
                "tags": data.get("tags", []),
                "image": data.get("image", ""),
            })
        else:
            member = find_item(content["team"]["members"], submission.get("item_id", ""))
            if member:
                for key in ("name", "role", "github_url", "lattes_url", "description", "tags"):
                    if key in data:
                        member[key] = data[key]
                if data.get("category") in valid_categories:
                    member["category"] = data["category"]
                if data.get("image"):
                    member["image"] = data["image"]

    save_site_content(content)
    mark_approved(submission_id)
    flash("Submissão aprovada e publicada no site.", "success")
    return redirect(url_for("admin_pending"))


@app.route("/admin/pending/<submission_id>/reject", methods=["POST"])
@admin_required
def admin_reject_submission(submission_id: str):
    submission = get_pending_item(submission_id)
    if not submission or submission.get("status") != "pending":
        flash("Submissão não encontrada ou já processada.", "danger")
        return redirect(url_for("admin_pending"))

    mark_rejected(submission_id)
    flash("Submissão rejeitada.", "warning")
    return redirect(url_for("admin_pending"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
