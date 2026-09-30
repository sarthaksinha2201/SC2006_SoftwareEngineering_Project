"""Event ingestion: new posts -> pre-filter -> LLM extraction -> validation -> venue
resolution -> merge and store. Runs every 6 hours; one run also purges ended events.

    python -m gowhere.ingest.run                      # one run now (the demo-day command)
    python -m gowhere.ingest.run --every-hours 6      # keep running, on the always-on host
    python -m gowhere.ingest.run --posts-file tests/fixtures/lepak/posts.json
    python -m gowhere.ingest.run --report             # yield rate of the recent runs
    python -m gowhere.ingest.run --posts-file tests/fixtures/lepak/posts.json \
        --replay-replies tests/fixtures/lepak/extractions.json   # rehearsal, no API key

Posts arrive in the S2 post-record contract (Sarthak.md), oldest first, newer than the
channel's marker. The marker only moves past a post once that post has been fully
handled and its events committed: if the LLM call or OneMap fails, the run stops for
that channel and those posts are tried again next time, never skipped.

Every discarded event is logged with its reason and counted, so the yield rate
(posts in -> events stored) can be reported. Log lines carry post ids and extracted
titles, never post text.
"""
import argparse
import json
import logging
import time
from collections import Counter
from pathlib import Path

from gowhere import config
from gowhere.adapters.http import HttpError
from gowhere.adapters.llm import LlmAdapter, LlmError, ReplayLlm
from gowhere.etl.geocode import SearchCache
from gowhere.etl.reference import load_venue_aliases
from gowhere.ingest.extract import Discard, extract_batch, validate
from gowhere.ingest.prefilter import has_date_like_text
from gowhere.lepak import sgt_now
from gowhere.lepak.store import EventStore
from gowhere.services.location import LocationService

log = logging.getLogger("gowhere.ingest")
LOG_FILE = config.LOG_DIR / "ingest.log"


def post_number(post):
    return int(post["post_id"].rsplit("/", 1)[1])


class FilePostSource:
    """Post records from a JSON file (fixtures, or a saved scrape), honouring since."""

    def __init__(self, path):
        self.records = json.loads(Path(path).read_text(encoding="utf-8"))

    def posts(self, channel, since_post_id=None):
        return sorted((p for p in self.records if p["channel"] == channel
                       and (since_post_id is None or post_number(p) > since_post_id)),
                      key=post_number)


class TelegramPostSource:
    """Sarthak's S2 scraper (gowhere.ingest.telegram), once it exists."""

    def posts(self, channel, since_post_id=None):
        try:
            from gowhere.ingest import telegram
        except ImportError:
            raise SystemExit("The Telegram scraper (S2, gowhere/ingest/telegram.py) is not "
                             "in the repo yet; run with --posts-file instead.")
        since = f"{channel}/{since_post_id}" if since_post_id is not None else None
        return telegram.fetch_posts(channel, since_post_id=since)


class Ingestor:
    def __init__(self, store, llm, locations, batch_size=config.LLM_BATCH_SIZE):
        self.store, self.llm, self.locations = store, llm, locations
        self.batch_size = batch_size

    def run(self, source, channels, now=None):
        """One ingestion run. Returns its counts (also recorded in the store)."""
        started = now or sgt_now()
        counts = Counter()
        discards = Counter()
        for channel in channels:
            self._channel(channel, source, started, counts, discards)
        counts["purged_ended"] = self.store.purge_ended(started)
        result = {**counts, "discarded": dict(discards)}
        self.store.record_run(started, now or sgt_now(), result)
        log.info("run finished: %s", json.dumps(result, sort_keys=True))
        return result

    def _channel(self, channel, source, now, counts, discards):
        posts = source.posts(channel, self.store.last_post_id(channel))
        counts["posts_seen"] += len(posts)
        batch = []
        for i, post in enumerate(posts):
            if not (post.get("text") or "").strip() or not has_date_like_text(post["text"]):
                counts["posts_prefiltered_out"] += 1
                continue
            batch.append(post)
            if len(batch) == self.batch_size:
                if not self._batch(channel, batch, now, counts, discards):
                    return
                batch = []
        if batch and not self._batch(channel, batch, now, counts, discards):
            return
        if posts:     # trailing pre-filtered posts are handled too
            self.store.commit_batch([], channel, post_number(posts[-1]), now)

    def _batch(self, channel, batch, now, counts, discards):
        """Extract, validate, place and store one batch. False if a service failed, in
        which case nothing from this batch is stored and the marker does not move."""
        try:
            extracted = extract_batch(batch, self.llm)
        except LlmError as e:
            counts["llm_failures"] += 1
            log.error("%s: LLM call failed for posts %s..%s; marker not advanced: %s",
                      channel, batch[0]["post_id"], batch[-1]["post_id"], e)
            return False
        counts["posts_sent_to_llm"] += len(batch)
        counts["events_extracted"] += len(extracted)
        with_events = {p["post_id"] for p, _ in extracted if p is not None}
        counts["posts_without_events"] += sum(p["post_id"] not in with_events for p in batch)
        keep = []
        for post, item in extracted:
            where = post["post_id"] if post else "?"
            try:
                event = validate(item, post, now)
                place = self.locations.place(event["venue"], event["address"])
                if place is None:
                    raise Discard("venue could not be placed on the map")
            except Discard as d:
                discards[str(d)] += 1
                log.info("discard %s: %s (%r)", where, d, str(item.get("title"))[:80])
                continue
            except HttpError as e:
                counts["onemap_failures"] += 1
                log.error("%s: OneMap failed while placing venues; marker not advanced: %s",
                          channel, e)
                return False
            keep.append({**event, "lat": place["lat"], "lon": place["lon"],
                         "place_name": place["name"]})
        added, merged = self.store.commit_batch(keep, channel, post_number(batch[-1]), now)
        counts["events_stored"] += added
        counts["events_merged"] += merged
        return True


def report(store, last=10):
    rows = store.db.execute("SELECT started_at, counts_json FROM ingest_run "
                            "ORDER BY id DESC LIMIT ?", (last,)).fetchall()
    for started, counts_json in rows:
        c = json.loads(counts_json)
        kept = c.get("events_stored", 0) + c.get("events_merged", 0)
        print(f"{started}  posts {c.get('posts_seen', 0)} (pre-filtered out "
              f"{c.get('posts_prefiltered_out', 0)})  events extracted "
              f"{c.get('events_extracted', 0)}, kept {kept}  discarded {c.get('discarded', {})}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--posts-file", help="read post records from this JSON file")
    ap.add_argument("--channel", action="append", help="only these channels")
    ap.add_argument("--every-hours", type=float, help="repeat forever at this interval")
    ap.add_argument("--report", action="store_true", help="print recent runs' yield")
    ap.add_argument("--replay-replies", help="answer from this {post_id: events} JSON instead "
                                              "of calling the LLM (rehearsal only)")
    args = ap.parse_args(argv)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)])
    store = EventStore()
    if args.report:
        report(store)
        return
    source = FilePostSource(args.posts_file) if args.posts_file else TelegramPostSource()
    if args.replay_replies:
        log.warning("replaying recorded replies from %s: no LLM is called", args.replay_replies)
        llm = ReplayLlm(json.loads(Path(args.replay_replies).read_text(encoding="utf-8")))
    else:
        llm = LlmAdapter()
    ingestor = Ingestor(store, llm,
                        LocationService(cache=SearchCache(config.CACHE_DIR / "onemap_search.sqlite"),
                                        aliases=load_venue_aliases()))
    channels = args.channel or config.LEPAK_CHANNELS
    while True:
        ingestor.run(source, channels)
        if not args.every_hours:
            return
        time.sleep(args.every_hours * 3600)


if __name__ == "__main__":
    main()
