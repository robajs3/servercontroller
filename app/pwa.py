"""PWA: manifest i service worker. Oba muszą być publiczne (bez logowania) i sw.js musi być serwowany z korzenia,
żeby jego zakres obejmował cały panel."""
import json
from flask import Blueprint, current_app, make_response, send_from_directory, url_for

pwa = Blueprint("pwa", __name__)

@pwa.get("/manifest.webmanifest")
def manifest():
    ic = lambda f: url_for("static", filename="pwa/" + f)
    data = {
        "id": "/", "name": "Panel serwerów", "short_name": "Panel", "lang": "pl",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#0f1115", "theme_color": "#0f1115",
        "icons": [
            {"src": ic("icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": ic("icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": ic("icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    r = make_response(json.dumps(data, ensure_ascii=False))
    r.mimetype = "application/manifest+json"
    r.headers["Cache-Control"] = "public, max-age=3600"
    return r

@pwa.get("/sw.js")
def service_worker():
    r = send_from_directory(current_app.static_folder, "sw.js", mimetype="text/javascript")
    r.headers["Cache-Control"] = "no-cache"          # przeglądarka ma zawsze sprawdzać, czy jest nowa wersja
    r.headers["Service-Worker-Allowed"] = "/"
    return r
