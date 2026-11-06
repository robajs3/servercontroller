import os, getpass, secrets
from datetime import timedelta
import click, pyotp, qrcode
from argon2 import PasswordHasher
from flask import Flask, g, jsonify, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, login_manager, csrf, limiter, migrate
from .models import User

def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],
        SQLALCHEMY_DATABASE_URI=os.environ["DATABASE_URL"],
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "1") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        MAIN_NAME=os.getenv("MAIN_NAME", "Serwer główny"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # Funnel
    db.init_app(app); csrf.init_app(app); limiter.init_app(app); migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    @login_manager.unauthorized_handler
    def _unauthorized():
        # API i żądania htmx dostają 401 (a nie przekierowanie na HTML logowania)
        if request.path.startswith("/api/") or request.headers.get("HX-Request"):
            r = jsonify(error="unauthorized"); r.status_code = 401
            r.headers["HX-Redirect"] = url_for("main.login")
            return r
        return redirect(url_for("main.login"))
    login_manager.user_loader(lambda uid: db.session.get(User, int(uid)))

    from .routes import bp
    app.register_blueprint(bp)
    from .docker_routes import dbp
    app.register_blueprint(dbp)
    from .camera import cam
    app.register_blueprint(cam)
    from .pwa import pwa
    app.register_blueprint(pwa)
    from .notifications import nbp
    app.register_blueprint(nbp)

    csp_header = "Content-Security-Policy-Report-Only" if os.getenv("CSP_REPORT_ONLY") == "1" else "Content-Security-Policy"

    @app.before_request
    def _nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _csp_ctx():
        return {"csp_nonce": g.get("csp_nonce", "")}

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "same-origin"
        # skrypty tylko z własnego origin + inline z nonce (bez 'unsafe-inline'/'unsafe-eval');
        # style inline dopuszczone (atrybuty style w szablonach)
        r.headers[csp_header] = (
            f"default-src 'self'; script-src 'self' 'nonce-{g.get('csp_nonce', '')}'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        if app.config["SESSION_COOKIE_SECURE"]:
            r.headers["Strict-Transport-Security"] = "max-age=31536000"
        return r

    @app.cli.command("init-db")
    def init_db():
        """Tworzy lub aktualizuje schemat (migracje). Bazę z poprzednich etapów (create_all, bez
        alembic_version) przejmuje przez stamp bazowej migracji 0001."""
        from flask_migrate import stamp, upgrade
        from sqlalchemy import inspect
        tables = set(inspect(db.engine).get_table_names())
        if "users" in tables and "alembic_version" not in tables:
            db.create_all()                 # dopełnia brakujące tabele (np. po pominiętych etapach)
            stamp(revision="0001")
        upgrade()

    @app.cli.command("unlock-user")
    @click.argument("username")
    def unlock_user(username):
        """Zdejmuje blokadę logowania z konta."""
        u = User.query.filter_by(username=username).first()
        if not u:
            raise click.ClickException("Nie ma takiego użytkownika")
        u.failed_count, u.locked_until = 0, None
        db.session.commit()
        click.echo("Konto odblokowane.")

    @app.cli.command("gen-vapid")
    def gen_vapid():
        """Generuje klucze VAPID dla powiadomień push (wklej do .env)."""
        from .push import generate_keys
        priv, pub = generate_keys()
        click.echo(f"VAPID_PRIVATE_KEY={priv}\nVAPID_PUBLIC_KEY={pub}\nVAPID_SUBJECT=mailto:twoj@adres.pl")

    @app.cli.command("create-user")
    @click.argument("username")
    def create_user(username):
        pw = getpass.getpass("Hasło (min. 12 znaków): ")
        if len(pw) < 12:
            raise click.ClickException("Za krótkie hasło")
        secret = pyotp.random_base32()
        db.session.add(User(username=username,
                            password_hash=PasswordHasher().hash(pw),
                            totp_secret=secret))
        db.session.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(username, issuer_name="Panel")
        qr = qrcode.QRCode(border=1); qr.add_data(uri); qr.print_ascii(invert=True)
        click.echo(f"\nZeskanuj QR w aplikacji 2FA. Sekret: {secret}")
    return app
