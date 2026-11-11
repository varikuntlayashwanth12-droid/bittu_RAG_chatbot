import os
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from rag_chatbot import DATA_DIR, ask_rag_chatbot

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
AUTH_SETTINGS = ("APP_USERNAME", "APP_PASSWORD", "FLASK_SECRET_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def missing_auth_settings():
    return [key for key in AUTH_SETTINGS if not os.environ.get(key)]


def auth_is_configured():
    return not missing_auth_settings()


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please sign in to use the document assistant."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def csrf_is_valid():
    expected = session.get("_csrf_token", "")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))


def list_documents():
    if not DATA_DIR.exists():
        return []

    return [
        {"name": path.name, "bytes": path.stat().st_size}
        for path in sorted(DATA_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS
    ]


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("home"))

    error = None
    missing_settings = missing_auth_settings()
    configured = not missing_settings
    if request.method == "POST":
        if not csrf_is_valid():
            error = "This sign-in form expired. Reload the page and try again."
        elif not configured:
            error = (
                "Sign-in is disabled. Missing settings in the project-root .env file: "
                f"{', '.join(missing_settings)}. Add them and restart the app."
            )
        else:
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            valid_username = secrets.compare_digest(
                username.encode("utf-8"), os.environ["APP_USERNAME"].encode("utf-8")
            )
            valid_password = secrets.compare_digest(
                password.encode("utf-8"), os.environ["APP_PASSWORD"].encode("utf-8")
            )
            if valid_username and valid_password:
                session.clear()
                session.permanent = True
                session["authenticated"] = True
                csrf_token()
                return redirect(url_for("home"))
            error = "That username and password do not match. Try again."

    return render_template(
        "login.html",
        error=error,
        auth_configured=configured,
        missing_settings=missing_settings,
    )


@app.post("/logout")
@login_required
def logout():
    if not csrf_is_valid():
        return "This sign-out form expired. Reload the page and try again.", 400
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def home():
    return render_template("index.html")


@app.get("/api/documents")
@login_required
def documents():
    return jsonify({"documents": list_documents()})


@app.post("/api/documents")
@login_required
def upload_document():
    if not csrf_is_valid():
        return jsonify({"error": "Your session expired. Reload the page and try again."}), 400

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Choose a PDF, TXT, or Markdown file to upload."}), 400

    filename = secure_filename(uploaded_file.filename)
    extension = Path(filename).suffix.lower()
    if not filename or extension not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Only PDF, TXT, and Markdown files are supported."}), 400

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    destination = DATA_DIR / filename
    if destination.exists():
        return jsonify({"error": f"A document named '{filename}' is already uploaded."}), 409

    uploaded_file.save(destination)
    return jsonify({"document": {"name": filename, "bytes": destination.stat().st_size}}), 201


@app.post("/api/ask")
@login_required
def ask():
    if not csrf_is_valid():
        return jsonify({"error": "Your session expired. Reload the page and try again."}), 400

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "Enter a question about your documents."}), 400
    if len(question) > 2000:
        return jsonify({"error": "Keep questions under 2,000 characters."}), 400

    try:
        answer = ask_rag_chatbot(question)
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except requests.exceptions.RequestException as exc:
        return jsonify({"error": f"Could not get a response from Ollama: {exc}"}), 502
    except Exception:
        app.logger.exception("Unexpected error while answering a question")
        return jsonify({"error": "Something went wrong while answering. Check the app log."}), 500

    return jsonify({"answer": answer})


@app.errorhandler(413)
def upload_too_large(_error):
    return jsonify({"error": "The file is too large. Maximum upload size is 25 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
