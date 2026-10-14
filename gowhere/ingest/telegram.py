"""S2 — Telegram scraper (Sarthak.md). Fetches posts from a public Telegram channel's
read-only web preview, no API key and no login:

    GET https://t.me/s/<channel>                 latest ~20 posts, oldest first
    GET https://t.me/s/<channel>?before=<id>      the ~20 posts immediately before <id>

requests + BeautifulSoup, as decided in DECISIONS.md (the Telegram API and a headless
browser were both considered and rejected). The only caller is
gowhere.ingest.run.TelegramPostSource.

    python -m gowhere.ingest.telegram --channel sgweekend --limit 20

Known gap: very long posts are reported (not confirmed against a real example) to be
truncated in this web view. No truncation marker was found in the 55 real posts used to
build tests/fixtures/telegram/*.html, so none is detected here. If a future fixture
shows one, add a check in _parse_page.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from gowhere.adapters.http import HttpError, RETRYABLE_STATUS, RateLimiter

PREVIEW_URL = "https://t.me/s/{channel}"
USER_AGENT = "Mozilla/5.0 (compatible; GoWhereBot/1.0; SC2006 student project)"
SGT = timezone(timedelta(hours=8))
MAX_PAGES = 50             # ~1,000 posts back; stops a pagination bug from looping forever
RATE_LIMIT_S = 1.0         # polite minimum interval between requests to a public endpoint


def post_number(post_id):
    """The numeric part of a post_id, e.g. "sgweekend/1234" -> 1234."""
    return int(post_id.rsplit("/", 1)[1])


def _get(session, channel, before, limiter, sleep):
    """One page of the web preview. Raises HttpError after one retry."""
    limiter.wait()
    url = PREVIEW_URL.format(channel=channel)
    params = {"before": before} if before else None
    last_error = None
    for attempt in range(2):
        try:
            resp = session.get(url, params=params, headers={"User-Agent": USER_AGENT},
                               timeout=10)
        except requests.RequestException as e:
            last_error = HttpError(f"{type(e).__name__}: {e}")
        else:
            if resp.status_code == 200:
                return resp.text
            last_error = HttpError(f"HTTP {resp.status_code}", status=resp.status_code)
            if resp.status_code not in RETRYABLE_STATUS:
                raise last_error
        if attempt == 0:
            sleep(1.0)
    raise last_error


def _parse_page(html, channel):
    """Posts on one page, oldest first. Also returns the lowest post number on the page
    (including media-only posts, which are skipped below but still set where the next
    page, if any, must start) -- or None if the page had no posts at all."""
    soup = BeautifulSoup(html, "html.parser")
    messages = soup.select("div.tgme_widget_message[data-post]")
    numbers = [post_number(m["data-post"]) for m in messages]
    records = []
    for msg, number in zip(messages, numbers):
        text_div = msg.select_one("div.tgme_widget_message_text")
        if text_div is None:
            continue                              # media-only post: nothing to extract
        for br in text_div.find_all("br"):
            br.replace_with("\n")
        text = text_div.get_text().strip()
        if not text:
            continue
        time_tag = msg.select_one("time.time[datetime]")
        if time_tag is None:
            continue                              # no timestamp: can't place this reliably
        posted_sgt = datetime.fromisoformat(time_tag["datetime"]).astimezone(SGT)
        links = [a["href"] for a in text_div.find_all("a", href=True)]
        records.append({
            "channel": channel,
            "post_id": f"{channel}/{number}",
            "posted_at": posted_sgt.isoformat(),
            "text": text,
            "links": links,
            "source_url": f"https://t.me/{channel}/{number}",
        })
    records.sort(key=lambda r: post_number(r["post_id"]))
    return records, (min(numbers) if numbers else None)


def fetch_posts(channel, since_post_id=None, limit=None, session=None, sleep=time.sleep):
    """Posts from a public Telegram channel, oldest first.

    since_post_id, e.g. "sgweekend/1234": only posts numbered higher are returned, and
    as many pages as needed are fetched to find them all.
    limit: used only when since_post_id is None (e.g. a first run, or the CLI below) --
    stop once at least this many posts have been collected. With neither, one page
    (Telegram's own ~20 most recent posts) is returned.
    """
    session = session or requests.Session()
    limiter = RateLimiter(RATE_LIMIT_S, sleep=sleep)
    since_number = post_number(since_post_id) if since_post_id else None
    collected = {}
    before = None
    for _ in range(MAX_PAGES):
        html = _get(session, channel, before, limiter, sleep)
        page, oldest = _parse_page(html, channel)
        for record in page:
            collected[record["post_id"]] = record
        if oldest is None:
            break                                  # empty page: start of the channel
        if since_number is not None:
            if oldest <= since_number:
                break
        elif limit is not None:
            if len(collected) >= limit:
                break
        else:
            break                                  # no cursor given: one page is enough
        before = oldest
    records = sorted(collected.values(), key=lambda r: post_number(r["post_id"]))
    if since_number is not None:
        records = [r for r in records if post_number(r["post_id"]) > since_number]
    elif limit is not None:
        records = records[-limit:]
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--channel", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--since", help="post_id, e.g. sgweekend/1234; only newer posts are returned")
    args = ap.parse_args(argv)
    posts = fetch_posts(args.channel, since_post_id=args.since, limit=args.limit)
    print(json.dumps(posts, indent=2, ensure_ascii=False))
    print(f"{len(posts)} posts", file=sys.stderr)


if __name__ == "__main__":
    main()
