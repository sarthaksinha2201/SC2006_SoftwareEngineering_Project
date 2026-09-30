"""The six screens. Where to Live is wired to the scoring engine; Where to Lepak is a
placeholder until the event-ingestion half exists."""
from flask import (Blueprint, current_app, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.datastructures import MultiDict

from gowhere.scoring.engine import InvalidRequest, NoFactorsLeft, ScoringEngine
from gowhere.scoring.registry import default_strategies
from gowhere.web.forms import FormError, parse_live_form
from gowhere.web.view_models import dropped_messages, results_view, setup_view

bp = Blueprint("web", __name__)


def _state():
    """This browser's server-side state. The cookie carries only an opaque session id."""
    store = current_app.extensions["gowhere"]["store"]
    if "sid" not in session:
        session["sid"] = store.new_id()
    return store.get(session["sid"])


def _engine(state):
    snapshot = current_app.extensions["gowhere"]["snapshot"]
    return ScoringEngine(default_strategies(state.router), snapshot), snapshot


@bp.get("/")
def home():
    return render_template("home.html")


@bp.get("/live")
def live_setup():
    state = _state()
    engine, snapshot = _engine(state)
    return render_template("live_setup.html", view=setup_view(engine, snapshot, state.last_request))


@bp.post("/live")
def live_submit():
    state = _state()
    engine, snapshot = _engine(state)
    form = MultiDict(request.form)
    try:
        areas, choices = parse_live_form(form, list(engine.strategies))
        engine.compare(areas, choices)     # validates; routes Commute once into the cache
    except (FormError, InvalidRequest) as e:
        return render_template("live_setup.html",
                               view=setup_view(engine, snapshot, form, error=str(e))), 400
    except NoFactorsLeft:
        pass                                # the results page explains which were dropped
    state.last_request = form
    return redirect(url_for("web.live_results"), code=303)


@bp.get("/live/results")
def live_results():
    state = _state()
    if state.last_request is None:
        return redirect(url_for("web.live_setup"))
    engine, snapshot = _engine(state)
    areas, choices = parse_live_form(state.last_request, list(engine.strategies))
    try:
        result = engine.compare(areas, choices)
    except NoFactorsLeft as e:
        return render_template("error.html", title="Nothing left to compare",
                               messages=dropped_messages(e.dropped)
                               + ["Every included factor was left out, so there is no ranking."]), 200
    return render_template("live_results.html", view=results_view(result, snapshot))


@bp.post("/live/check")
def live_check():
    """Selection-time warning: which factors would be dropped, before the user submits.
    Commute is never checked here (it would call OneMap), and its fields are ignored."""
    state = _state()
    engine, _ = _engine(state)
    try:
        areas, choices = parse_live_form(request.form, list(engine.strategies), skip={"commute"})
        if not choices:
            return jsonify(warnings=[], incomplete="Include at least one factor.")
        result = engine.compare(areas, choices)
        return jsonify(warnings=dropped_messages(result["dropped"]), incomplete=None)
    except NoFactorsLeft as e:
        return jsonify(warnings=dropped_messages(e.dropped)
                       + ["No factor would have data for every selected area."], incomplete=None)
    except (FormError, InvalidRequest) as e:
        return jsonify(warnings=[], incomplete=str(e))


# ---- Where to Lepak: not built yet ----

@bp.get("/lepak")
@bp.get("/lepak/results")
@bp.get("/lepak/events/<event_id>")
def lepak_placeholder(event_id=None):
    return render_template("lepak_placeholder.html"), 501
