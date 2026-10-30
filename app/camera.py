import os, threading, time
from datetime import datetime
import requests
from flask import Blueprint, Response, abort, render_template, request
from flask_login import login_required
from .extensions import limiter
from .routes import audit

cam = Blueprint("cam", __name__)
URL = os.getenv("CAMERA_URL", "").rstrip("/")             # puste = kamera wyłączona
SRC = os.getenv("CAMERA_SRC", "cam")
MAX_SECONDS = int(os.getenv("CAMERA_STREAM_MAX_SECONDS", 900))
SLOTS = threading.BoundedSemaphore(int(os.getenv("CAMERA_MAX_STREAMS", 2)))

@cam.app_context_processor
def _ctx():
    return {"camera_enabled": bool(URL)}

def _need():
    if not URL:
        abort(404)

@cam.route("/camera")
@login_required
def camera_page():
    _need()
    return render_template("camera.html", max_s=MAX_SECONDS)

@cam.route("/camera/snapshot")
@login_required
@limiter.limit("120/minute")
def snapshot():
    _need()
    try:
        r = requests.get(f"{URL}/api/frame.jpeg", params={"src": SRC}, timeout=8)
        r.raise_for_status()
        if r.content[:2] != b"\xff\xd8":
            raise ValueError("to nie jest JPEG")
    except (requests.RequestException, ValueError):
        return Response("Kamera niedostępna", 502, mimetype="text/plain")
    h = {"Cache-Control": "no-store"}
    if request.args.get("download"):
        audit("camera snapshot download")
        h["Content-Disposition"] = f'attachment; filename="kamera-{datetime.now():%Y%m%d-%H%M%S}.jpg"'
    return Response(r.content, mimetype="image/jpeg", headers=h)

@cam.route("/camera/stream")
@login_required
@limiter.limit("20/minute")
def stream():
    """Proxy MJPEG z go2rtc. Zajmuje jeden wątek gunicorna na czas podglądu, dlatego: limit
    równoległych podglądów i twardy limit czasu (zapomniana karta nie blokuje serwera)."""
    _need()
    if not SLOTS.acquire(blocking=False):
        return Response("Zbyt wiele podglądów naraz", 429, mimetype="text/plain")
    try:
        up = requests.get(f"{URL}/api/stream.mjpeg", params={"src": SRC}, stream=True, timeout=(3, 10))
        up.raise_for_status()
    except requests.RequestException:
        SLOTS.release()
        return Response("Kamera niedostępna", 502, mimetype="text/plain")
    audit("camera stream")

    def gen():
        t0 = time.monotonic()
        try:
            for chunk in up.iter_content(chunk_size=4096):
                yield chunk
                if time.monotonic() - t0 > MAX_SECONDS:
                    break
        except requests.RequestException:
            pass
        finally:
            up.close()
            SLOTS.release()
    ctype = up.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame")
    return Response(gen(), mimetype=ctype, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
