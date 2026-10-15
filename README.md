# GoWhere

SC2006 Team 5. Compare Singapore neighbourhoods (**Where to Live**) and find events near
you (**Where to Lepak**).

## Run it on your laptop

You need Python 3.13. On macOS/Linux:

```bash
git clone https://github.com/sarthaksinha2201/SC2006_SoftwareEngineering_Project.git
cd SC2006_SoftwareEngineering_Project
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m gowhere.serve
```

Then open **http://127.0.0.1:8000**. Stop the server with Ctrl+C.

On Windows, use `py -3.13 -m venv .venv`, then `.venv\Scripts\pip install -r requirements.txt`
and `.venv\Scripts\python -m gowhere.serve`.

The neighbourhood data (`data/snapshot.db`) and the events (`data/events.db`) are in the
repo, so nothing needs downloading or building.

## API keys (optional)

The app runs without any keys. Without them, some features fall back:

| Without | What you see |
|---|---|
| `ONEMAP_EMAIL` + `ONEMAP_PASSWORD` | Commute is left out of Where to Live. Lepak shows straight-line distances instead of travel times and routes. |
| `LTA_DATAMALL_KEY` | Lepak's drive mode shows "Parking information unavailable". |
| `OPENAI_API_KEY` | You can't fetch new events; the app shows the ones already in the repo. |

To enable a feature, create a file named `.env` in the project folder with the keys you
have, one per line, for example `ONEMAP_EMAIL=you@example.com`. The `.env` file is ignored
by git. Never commit it, and never paste keys into chat.

## Try the demo

Follow section 3 of [docs/demo.md](docs/demo.md). It walks through Where to Live with
Queenstown, Tampines, Punggol and Bedok, then a Lepak search from postal code 238801.
Any 2 to 4 of the 32 neighbourhoods work. Changi, Downtown Core and Tanglin have too few
HDB resales to score Housing Affordability, and the app tells you so.

## Other commands

```bash
.venv/bin/python -m pytest -q                       # tests: no network or keys needed
.venv/bin/python -m gowhere.ingest.run              # fetch new events (needs OPENAI_API_KEY)
.venv/bin/python -m gowhere.lepak.images            # venue photos for new events (no key)
.venv/bin/python scripts/make_category_art.py       # redraw the category banners
.venv/bin/python -m gowhere.serve --host 0.0.0.0    # let phones on the same Wi-Fi open it
```

Event cards show a freely-licensed photograph of the venue from Wikipedia, falling back
to category artwork. Both live in the repo, so the cards work offline. After ingesting
new events, run `gowhere.lepak.images` to fetch pictures for any new venues; correct a
wrong match by naming the right article in `data/reference/venue_images.csv`.

More detail: [docs/demo.md](docs/demo.md) (running and demo script),
[DECISIONS.md](DECISIONS.md) (why things are the way they are).
