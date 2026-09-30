"""Flask app factory. The app reads data/snapshot.db (read-only) and data/events.db, and
calls its External Services at request time: OneMap routing (Commute, Lepak travel
times) and LTA DataMall carpark availability. It never calls a bulk Data Source."""
import logging
import os
import secrets

from flask import Flask, render_template

from gowhere import config
from gowhere.lepak import sgt_now
from gowhere.lepak.parking import ParkingService
from gowhere.lepak.routing import EventRouter
from gowhere.scoring.commute import CommuteRouter
from gowhere.services.location import LocationService
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
        EVENTS_PATH=config.EVENTS_PATH,
        LOCATION_FACTORY=LocationService.for_session,   # per session: postal lookups in memory only
        EVENT_ROUTER_FACTORY=EventRouter,     # per session
        PARKING_FACTORY=ParkingService,       # one per app: public data, shared cache
        NOW=sgt_now,
    )
    app.config.update(overrides or {})
    app.extensions["gowhere"] = {
        "snapshot": Snapshot(app.config["SNAPSHOT_PATH"]),
        "store": SessionStore(router_factory=app.config["ROUTER_FACTORY"]),
        "parking": app.config["PARKING_FACTORY"](),
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
