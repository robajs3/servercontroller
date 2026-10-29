import os, getpass
from datetime import timedelta
import click, pyotp, qrcode
from argon2 import PasswordHasher
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, login_manager, csrf, limiter
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
    db.init_app(app); csrf.init_app(app); limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    login_manager.user_loader(lambda uid: db.session.get(User, int(uid)))

    from .routes import bp
    app.register_blueprint(bp)
    from .docker_routes import dbp
    app.register_blueprint(dbp)

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "same-origin"
        return r

    @app.cli.command("init-db")
    def init_db():
        db.create_all()

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
