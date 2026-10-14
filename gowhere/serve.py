"""Run GoWhere: one process, Waitress serving the web app, and optionally the event
ingestion schedule on a background thread (DECISIONS.md section 4: one always-on host).

    python -m gowhere.serve                          # web app only (the default)
    python -m gowhere.serve --ingest-every-hours 6   # demo-day setting: also ingest
    python -m gowhere.serve --port 8080 --host 0.0.0.0

It must stay one process: each user's session state (the postal code, the route cache,
the last search) lives in this process's memory. Waitress runs threads, not processes,
so that holds.

The schedule is off by default. To fetch new events by hand while the server runs,
use the separate command `python -m gowhere.ingest.run` (SQLite lets the two share
data/events.db).
"""
import argparse
import logging
import threading

from gowhere import config
from gowhere.ingest import run as ingest_run
from gowhere.web import create_app

log = logging.getLogger("gowhere.serve")


def start_ingestion(every_hours, channels=None, stop=None):
    """A daemon thread running ingestion now and then every `every_hours`. The
    pipeline is built inside the thread, which owns its SQLite connections."""
    stop = stop or threading.Event()

    def loop():
        ingestor = ingest_run.default_ingestor()
        ingest_run.run_on_schedule(ingestor, ingest_run.TelegramPostSource(),
                                   channels or config.LEPAK_CHANNELS, every_hours, stop=stop)

    thread = threading.Thread(target=loop, name="ingestion", daemon=True)
    thread.start()
    return thread, stop


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", default="127.0.0.1",
                    help="0.0.0.0 to let phones on the same network connect")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--ingest-every-hours", type=float, default=None,
                    help="also ingest events on this schedule (off by default; 6 on demo day)")
    args = ap.parse_args(argv)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(config.LOG_DIR / "serve.log")])
    app = create_app()
    if args.ingest_every_hours:
        start_ingestion(args.ingest_every_hours)
        log.info("ingestion scheduled every %s h", args.ingest_every_hours)
    else:
        log.info("ingestion schedule off; run python -m gowhere.ingest.run to fetch events")
    import waitress
    log.info("serving on http://%s:%s", args.host, args.port)
    waitress.serve(app, host=args.host, port=args.port, threads=args.threads)


if __name__ == "__main__":
    main()
