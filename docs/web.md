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
| `GET /lepak`, `/lepak/results`, `/lepak/events/<id>` | Placeholder, 501, until event ingestion exists |

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

See [frontend-notes.md](frontend-notes.md) for where each note sits and for the postal-code rules.
