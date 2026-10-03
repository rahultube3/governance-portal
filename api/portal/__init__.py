from flask import Flask
from flask_cors import CORS

from portal.auth import load_user
from portal.config import API_PREFIX, CHAT_MODEL, DB_PATH, load_secret_key
from portal.db import close_db
from portal.routes import BLUEPRINTS


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=load_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE=DB_PATH,
        CHAT_MODEL=CHAT_MODEL,
    )
    CORS(app)
    app.before_request(load_user)
    app.teardown_appcontext(close_db)
    for bp in BLUEPRINTS:
        app.register_blueprint(bp, url_prefix=API_PREFIX)
    return app
