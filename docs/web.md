# Web app (backend half)

## Run

```bash
python -m gowhere.etl.build_snapshot            # data/snapshot.db must exist
GOWHERE_SECRET_KEY=<random string> flask --app "gowhere.web:create_app()" run
```

- **Run a single process.** Threads are fine. Session state, including each user's commute route cache, lives in that process's memory, matching DECISIONS.md section 4 (one host).
- **HTTPS:** set `GOWHERE_HTTPS=1` in production so the session cookie is marked Secure.

## Routes

| Route | Screen |
|---|---|
| `GET /` | Home |
| `GET /live` | Where to Live setup, refilled from this session's last submission |
| `POST /live` | Validates the form and runs the comparison (Commute routes here, into the session cache), then redirects 303 to results. An invalid form re-renders setup with a 400 and a message. |
| `GET /live/results` | Results for this session's last submission |
| `POST /live/check` | Selection-time warning: JSON `{"warnings": [...], "incomplete": msg or null}`. Never checks Commute. |
| `GET /lepak` | Where to Lepak search, refilled from this session's last search |
| `POST /lepak` | Validates, looks up the starting point, filters by straight line, routes (at most 50), then redirects 303 to results. An invalid search, an unknown postal code, OneMap being down, or more than 50 candidates re-renders the search page with a 400 and a message. |
| `GET /lepak/results?sort=&category=&page=` | This session's last search, reordered. Sort, chip and page only reorder the saved results and make no external call. |
| `GET /lepak/events/<id>` | Event detail. From this session's search it has the travel time, route and (drive mode) freshly cached parking. Opened directly, it shows the event without travel. Unknown or ended: 404. |

POST then redirect-then-GET keeps the results URL free of any user input.

## Templates and the contract

- **Placeholders:** the templates in `gowhere/web/templates/` are unstyled and marked as such; Sarthak's S3 templates replace them.
- **Context:** templates receive `view`:
  - on the setup page, `view_models.setup_view()`;
  - on the results page, `view_models.results_view()`.
- **Fixtures:** `tests/fixtures/mock_results.json` and `mock_results_all_scored.json` are real examples of the results context. Build the results page against them.
- **Regenerating:** `python -m gowhere.web.mock` regenerates both from the current snapshot.
- **Drift check:** `tests/test_web.py` fails if the view model's shape drifts from the fixtures.

`mock_results.json` shows the degraded states:
- Housing dropped, naming Changi and Tengah;
- Changi's small-area note;
- far-from-rail notes on Changi and Tengah;
- the Commute, CHAS, supermarket and OpenStreetMap factor notes.

It can't also show the housing-window note, because every small area lacks resales, so Housing is always dropped when one is selected. `mock_results_all_scored.json` shows all six factors scored, with the housing-window note.

### Where to Lepak

- **Context:** each template receives `view`:
  - on the search page, `lepak_views.setup_view()`;
  - on the results page, `lepak_views.results_view()`;
  - on the detail page, `lepak_views.event_view()`.
- **Fixtures:** `tests/fixtures/mock_lepak_results.json` and `mock_lepak_event.json` are real examples of the two contexts. They come from the ingestion fixtures, with fixed travel times.
- **What the results fixture shows:**
  - 9 events sorted by travel time;
  - one "Travel time unavailable" event, listed last, with its note;
  - the chips with their counts;
  - the sort links.
- **What the detail fixture shows:** drive mode, with "Parking information unavailable". That is what every drive search shows until there is a DataMall key.
- **The map:** `view.map` is GeoJSON in lon/lat order. It holds the route line (`kind: "route"`, when there is one) and the venue point (`kind: "venue"`).
- **Starting point:** it is posted with the form. "Use my location" fills the hidden `lat` and `lon` fields from the browser. Neither the postal code nor the coordinates may ever go into a link, a query string or the cookie.
- **Escaping:** event text comes from public posts. Jinja escapes it; keep it that way and never use `|safe` on event fields.

See [frontend-notes.md](frontend-notes.md) for where each note sits and for the postal-code rules.
