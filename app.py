import os
import secrets
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text


db = SQLAlchemy()

load_dotenv()


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    repo_name = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    report_date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_name": self.project_name,
            "repo_name": self.repo_name,
            "title": self.title,
            "detail": self.detail,
            "report_date": self.report_date.isoformat(),
            "source": self.source,
            "created_at": self.created_at.isoformat() + "Z",
        }


def normalize_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    return raw_url


def get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def check_database_connection() -> dict:
    db.session.execute(text("SELECT 1"))
    report_count = db.session.query(Report.id).count()
    return {
        "status": "ok",
        "report_count": report_count,
    }


def build_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-before-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(get_required_env("DATABASE_URL"))
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["APP_API_KEY"] = os.environ.get("APP_API_KEY", "")

    db.init_app(app)

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def get_api_key() -> str:
    return os.environ.get("APP_API_KEY", "")


def is_authorized_request() -> bool:
    expected_key = get_api_key()
    if not expected_key:
        return False

    provided_key = request.headers.get("X-API-Key", "")
    if not provided_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            provided_key = auth_header[7:].strip()

    return secrets.compare_digest(provided_key, expected_key)


def require_api_key(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not is_authorized_request():
            return jsonify({"error": "Unauthorized"}), 401
        return view_func(*args, **kwargs)

    return wrapped


def require_dashboard_login(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if session.get("dashboard_authenticated"):
            return view_func(*args, **kwargs)
        return redirect(url_for("login", next=request.path))

    return wrapped


def parse_report_date(value: str | None):
    if not value:
        return datetime.utcnow().date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate_payload(payload: dict) -> tuple[dict | None, str | None]:
    required_fields = ["project_name", "repo_name", "title", "detail"]
    for field in required_fields:
        value = payload.get(field, "")
        if not isinstance(value, str) or not value.strip():
            return None, f"'{field}' is required."

    try:
        report_date = parse_report_date(payload.get("report_date"))
    except ValueError:
        return None, "'report_date' must use YYYY-MM-DD."

    cleaned = {
        "project_name": payload["project_name"].strip(),
        "repo_name": payload["repo_name"].strip(),
        "title": payload["title"].strip(),
        "detail": payload["detail"].strip(),
        "report_date": report_date,
        "source": str(payload.get("source", "")).strip() or None,
    }
    return cleaned, None


def register_routes(app: Flask) -> None:
    @app.route("/health")
    def health():
        if not get_api_key():
            return jsonify(
                {
                    "status": "misconfigured",
                    "checks": {
                        "api_key": {"status": "error", "message": "APP_API_KEY is not set"},
                        "database": {"status": "unknown"},
                    },
                }
            ), 500

        try:
            database_check = check_database_connection()
        except Exception as exc:
            return jsonify(
                {
                    "status": "error",
                    "checks": {
                        "api_key": {"status": "ok"},
                        "database": {"status": "error", "message": str(exc)},
                    },
                }
            ), 500

        return jsonify(
            {
                "status": "ok",
                "checks": {
                    "api_key": {"status": "ok"},
                    "database": database_check,
                },
            }
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        expected_key = get_api_key()
        if not expected_key:
            abort(500, description="APP_API_KEY is not configured.")

        next_path = request.args.get("next") or url_for("dashboard")
        if request.method == "POST":
            submitted_key = request.form.get("api_key", "")
            if secrets.compare_digest(submitted_key, expected_key):
                session["dashboard_authenticated"] = True
                return redirect(next_path)
            flash("Invalid API key.")

        return render_template("login.html")

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/")
    @require_dashboard_login
    def dashboard():
        query = request.args.get("q", "").strip()
        reports_query = Report.query
        if query:
            like = f"%{query}%"
            reports_query = reports_query.filter(
                or_(
                    Report.project_name.ilike(like),
                    Report.repo_name.ilike(like),
                    Report.title.ilike(like),
                )
            )

        reports = reports_query.order_by(Report.report_date.desc(), Report.created_at.desc()).all()
        return render_template("dashboard.html", reports=reports, query=query)

    @app.route("/reports/<int:report_id>")
    @require_dashboard_login
    def report_detail(report_id: int):
        report = Report.query.get_or_404(report_id)
        return render_template("report_detail.html", report=report)

    @app.get("/api/reports")
    @require_api_key
    def list_reports():
        reports = Report.query.order_by(Report.report_date.desc(), Report.created_at.desc()).all()
        return jsonify([report.to_dict() for report in reports])

    @app.get("/api/reports/<int:report_id>")
    @require_api_key
    def get_report(report_id: int):
        report = Report.query.get_or_404(report_id)
        return jsonify(report.to_dict())

    @app.post("/api/reports")
    @require_api_key
    def create_report():
        payload = request.get_json(silent=True) or {}
        cleaned, error = validate_payload(payload)
        if error:
            return jsonify({"error": error}), 400

        report = Report(**cleaned)
        db.session.add(report)
        db.session.commit()
        return jsonify({"message": "Report stored.", "report": report.to_dict()}), 201


app = build_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
