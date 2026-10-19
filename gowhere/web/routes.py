"""The nine screens: Where to Live (setup, results) on the scoring engine, Where to
Lepak (search, results, event detail) on the event store, and Where to Eat (search,
results, place detail) on the place list."""
from flask import (Blueprint, current_app, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.datastructures import MultiDict

from gowhere.adapters.http import HttpError
from gowhere.eat import ratings as eat_ratings
from gowhere.eat import search as eat_search
from gowhere.eat.hours import status as hours_status
from gowhere.eat.store import PlaceStore
from gowhere.lepak.search import InvalidSearch, TooManyEvents, search
from gowhere.lepak.store import EventStore
from gowhere.scoring.engine import InvalidRequest, NoFactorsLeft, ScoringEngine
from gowhere.scoring.registry import default_strategies
from gowhere.services.location import OfflinePostalNotFound
from gowhere.web.forms import FormError, parse_live_form
from gowhere.web import eat_views, lepak_views
from gowhere.web.view_models import dropped_messages, picker_map, results_view, setup_view

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


@bp.get("/live/areas.geojson")
def live_areas():
    """The setup screen's map picker reads its polygons here.

    The same bytes for everyone and fixed by the snapshot, so it is cached hard; the
    snapshot's build date busts it. Same-origin, so the picker still loads with the
    network off.
    """
    snapshot = current_app.extensions["gowhere"]["snapshot"]
    response = jsonify(picker_map(snapshot))
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = f'"areas-{snapshot.meta()["generated_at"]}"'
    return response


def as_sentence(error):
    """Validation messages are written as fragments ("select 2 to 4 neighbourhoods") so
    they compose; on the page each one stands alone, so it is shown as a sentence."""
    text = str(error)
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "?", "!")) else ".")


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
                               view=setup_view(engine, snapshot, form, error=as_sentence(e))), 400
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
    return render_template("live_results.html",
                           view=results_view(result, snapshot, all_factors=engine.factors()))


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


# ---- Where to Lepak ----

def _lepak(state):
    cfg = current_app.config
    if state.locations is None:
        state.locations = cfg["LOCATION_FACTORY"]()
        state.event_router = cfg["EVENT_ROUTER_FACTORY"]()
    return state


def _events():
    return EventStore(current_app.config["EVENTS_PATH"])


OFFLINE_POSTAL = ("OneMap can't be reached right now. Without it we can only look up HDB "
                  "block postal codes, and this one isn't one, so it couldn't be checked. "
                  "Try the postal code of a nearby HDB block, use your location, or try "
                  "again shortly.")
ONEMAP_DOWN = ("OneMap can't be reached right now, so we can't look up your starting point. "
               "Please try again shortly.")
POSTAL_NOT_FOUND = "We couldn't find that postal code. Check it and try again."


def _lepak_error(form, message):
    return render_template("lepak_setup.html",
                           view=lepak_views.setup_view(form, error=message)), 400


@bp.get("/lepak")
def lepak_setup():
    state = _state()
    form = state.lepak["form"] if state.lepak else None
    return render_template("lepak_setup.html", view=lepak_views.setup_view(form))


@bp.post("/lepak")
def lepak_submit():
    state = _lepak(_state())
    form = MultiDict(request.form)
    now = current_app.config["NOW"]()
    try:
        req = lepak_views.parse_lepak_form(form)
        kind, value = req["origin"]
        if kind == "postal":
            origin = state.locations.postal(value)
            if origin is None:
                raise InvalidSearch(POSTAL_NOT_FOUND)
        else:
            origin = value
        parking = current_app.extensions["gowhere"]["parking"] if req["mode"] == "drive" else None
        found = search(_events().events(now), origin, req["categories"], req["date_option"],
                       req["mode"], req["max_minutes"], state.event_router, now, parking=parking)
    except InvalidSearch as e:
        return _lepak_error(form, str(e))
    except TooManyEvents as e:
        return _lepak_error(form, lepak_views.too_many_message(e.count))
    except OfflinePostalNotFound:
        return _lepak_error(form, OFFLINE_POSTAL)
    except HttpError:
        return _lepak_error(form, ONEMAP_DOWN)
    # The starting point stays in this session's memory: it marks the route map's start.
    state.lepak = {"form": form, "request": req, "search": found, "origin": origin}
    return redirect(url_for("web.lepak_results"), code=303)


@bp.get("/lepak/results")
def lepak_results():
    """Sort, hidden categories and page come from the query string and only reorder the
    saved results: nothing here calls an external service."""
    state = _state()
    if state.lepak is None:
        return redirect(url_for("web.lepak_setup"))
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    view = lepak_views.results_view(state.lepak, request.args.get("sort"),
                                    request.args.getlist("hide"), page,
                                    current_app.config["NOW"](), _events().last_updated())
    state.lepak["view_state"] = view["view_state"]
    return render_template("lepak_results.html", view=view)


@bp.get("/lepak/events/<int:event_id>")
def lepak_event(event_id):
    state = _state()
    now = current_app.config["NOW"]()
    saved = state.lepak
    found = next((r for r in saved["search"]["results"] if r["id"] == event_id), None) if saved else None
    if found is not None:
        mode = saved["request"]["mode"]
        if mode == "drive":        # refreshed here (cached 2 min), never on sort or chips
            found = {**found, "parking": current_app.extensions["gowhere"]["parking"].near(
                found["lat"], found["lon"])}
        return render_template("event_detail.html", view=lepak_views.event_view(
            found, mode, now, back=saved.get("view_state"), origin=saved.get("origin")))
    event = _events().event(event_id)
    if event is None or event["ends_at"] < now.strftime("%Y-%m-%d %H:%M"):
        return render_template("error.html", title="Event not found",
                               messages=["It may have ended or been removed."]), 404
    return render_template("event_detail.html", view=lepak_views.event_view(event, None, now))


# ---- Where to Eat ----

def _places():
    """The place list, read once per process (gowhere.eat.store)."""
    ext = current_app.extensions["gowhere"]
    if ext.get("places") is None:
        ext["places"] = PlaceStore.load(current_app.config["EAT_PATH"])
    return ext["places"]


def _eat_error(form, message):
    return render_template("eat_setup.html",
                           view=eat_views.setup_view(form, error=message)), 400


@bp.get("/eat")
def eat_setup():
    state = _state()
    form = state.eat["form"] if state.eat else None
    return render_template("eat_setup.html", view=eat_views.setup_view(form))


@bp.post("/eat")
def eat_submit():
    state = _lepak(_state())        # the same per-session location lookups and router
    form = MultiDict(request.form)
    now = current_app.config["NOW"]()
    try:
        req = eat_views.parse_eat_form(form)
        kind, value = req["origin"]
        if kind == "postal":
            origin = state.locations.postal(value)
            if origin is None:
                raise eat_search.InvalidSearch(POSTAL_NOT_FOUND)
        else:
            origin = value
        parking = current_app.extensions["gowhere"]["parking"] if req["mode"] == "drive" else None
        found = eat_search.search(_places().places, origin, req["cuisines"], req["tiers"],
                                  req["when"], req["mode"], req["max_minutes"],
                                  state.event_router, now, parking=parking)
        # Ratings for every timed place, so "Highest rated" sorts them all, not just a page.
        eat_ratings.attach(found["results"], current_app.config["RATINGS_FACTORY"]())
    except eat_search.InvalidSearch as e:
        return _eat_error(form, str(e))
    except OfflinePostalNotFound:
        return _eat_error(form, OFFLINE_POSTAL)
    except HttpError:
        return _eat_error(form, ONEMAP_DOWN)
    # As for Lepak: the starting point stays in this session's memory only.
    state.eat = {"form": form, "request": req, "search": found, "origin": origin}
    return redirect(url_for("web.eat_results"), code=303)


@bp.get("/eat/results")
def eat_results():
    """Sort, hidden cuisines and page only reorder the saved results: no external call."""
    state = _state()
    if state.eat is None:
        return redirect(url_for("web.eat_setup"))
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    view = eat_views.results_view(state.eat, request.args.get("sort"),
                                  request.args.getlist("hide"), page,
                                  current_app.config["NOW"](), _places().meta)
    state.eat["view_state"] = view["view_state"]
    return render_template("eat_results.html", view=view)


@bp.get("/eat/places/<int:place_id>")
def eat_place(place_id):
    state = _state()
    saved = state.eat
    meta = _places().meta
    found = next((r for r in saved["search"]["results"] if r["id"] == place_id), None) if saved else None
    if found is not None:
        mode = saved["request"]["mode"]
        if mode == "drive":        # refreshed here (cached 2 min), never on sort or chips
            found = {**found, "parking": current_app.extensions["gowhere"]["parking"].near(
                found["lat"], found["lon"])}
        return render_template("eat_place.html", view=eat_views.place_view(
            found, mode, back=saved.get("view_state"), origin=saved.get("origin"), meta=meta))
    place = _places().get(place_id)
    if place is None:
        return render_template("error.html", title="Place not found", messages=[]), 404
    now = current_app.config["NOW"]()
    plain = {**place, "route": None, "distance_m": None,
             "open": hours_status(place["opening_hours"], now)}
    return render_template("eat_place.html", view=eat_views.place_view(plain, None, meta=meta))
