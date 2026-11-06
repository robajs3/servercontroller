"""Serwowanie frontendu (React, katalog static/spa po `npm run build`) i endpoint sesji."""
import os
from flask import Blueprint, abort, current_app, jsonify, send_from_directory
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from . import agents

spa = Blueprint("spa", __name__)
SPA_DIR = os.path.join(os.path.dirname(__file__), "static", "spa")


@spa.get("/api/session")
def session_info():
    """Publiczny: frontend pyta, czy jest zalogowany, i dostaje token CSRF (cookie sesji ustawia się tu)."""
    from . import camera
    ok = current_user.is_authenticated
    r = jsonify(authenticated=ok, csrf=generate_csrf(),
                user=current_user.username if ok else None,
                main_name=current_app.config["MAIN_NAME"] if ok else None,
                camera_enabled=bool(camera.URL) if ok else False,
                camera_max_seconds=camera.MAX_SECONDS,
                agents=[{"key": a["key"], "name": a["name"]} for a in agents.AGENTS.values()] if ok else [])
    r.headers["Cache-Control"] = "no-store"
    return r


@spa.route("/", defaults={"path": ""})
@spa.route("/<path:path>")
def index(path):
    if path.startswith(("api/", "static/")) or not os.path.isfile(os.path.join(SPA_DIR, "index.html")):
        abort(404)
    r = send_from_directory(SPA_DIR, "index.html")
    r.headers["Cache-Control"] = "no-cache"
    return r
