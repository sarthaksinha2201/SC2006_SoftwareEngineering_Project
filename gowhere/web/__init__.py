"""Flask app factory. The app reads only data/snapshot.db (read-only) and calls OneMap
routing for Commute at request time; it never calls a bulk Data Source."""
import logging
import os
import secrets

from flask import Flask, render_template

from gowhere import config
from gowhere.scoring.commute import CommuteRouter
from gowhere.snapshot import Snapshot
from gowhere.web.session_store import SessionStore

log = logging.getLogger(__name__)


def create_app(overrides=None):
    app = Flask(__name__)
    config.load_dotenv()
    secret = os.getenv("GOWHERE_SECRET_KEY")
    if not secret:
        log.warning("GOWHERE_SECRET_KEY not set; using a random key (sessions reset on restart)")
    app.config.update(
        SECRET_KEY=secret or secrets.token_hex(32),
        SNAPSHOT_PATH=config.SNAPSHOT_PATH,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("GOWHERE_HTTPS") == "1",
        ROUTER_FACTORY=CommuteRouter,
    )
    app.config.update(overrides or {})
    app.extensions["gowhere"] = {
        "snapshot": Snapshot(app.config["SNAPSHOT_PATH"]),
        "store": SessionStore(router_factory=app.config["ROUTER_FACTORY"]),
    }

    from gowhere.web.routes import bp
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", title="Page not found", messages=[]), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("error.html", title="Something went wrong",
                               messages=["Please try again."]), 500

    return app
