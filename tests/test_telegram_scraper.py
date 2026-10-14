"""S2 Telegram scraper (Sarthak.md): parses three real, unmodified page snapshots saved
under tests/fixtures/telegram/ (55 real posts across both confirmed channels, plus one
`before=` page to exercise pagination). No network call is made here -- every test
builds a fake session that serves the saved HTML. Must pass with the wifi off.
"""
import pytest

from gowhere.adapters.http import HttpError
from gowhere.config import ROOT
from gowhere.ingest.telegram import _parse_page, fetch_posts, post_number

FIXTURES = ROOT / "tests" / "fixtures" / "telegram"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


SGWEEKEND_LATEST = load("sgweekend_latest.html")      # posts 3814..3835, oldest first
SGWEEKEND_BEFORE = load("sgweekend_before.html")       # posts 3792..3813 (before=3814)
SGWHERETO_LATEST = load("sgwhereto_latest.html")       # posts 4494..4513 (15 real)


class Resp:
    def __init__(self, status, body=""):
        self.status_code, self.text = status, body


class FakeSession:
    """Serves canned HTML by the `before` param, like the real t.me/s/<channel> paging."""

    def __init__(self, pages, fail_times=0):
        self.pages, self.fail_times, self.calls = pages, fail_times, []

    def get(self, url, params=None, headers=None, timeout=None):
        before = (params or {}).get("before")
        self.calls.append(before)
        if len(self.calls) <= self.fail_times:
            return Resp(503)
        return Resp(200, self.pages[before])


def no_sleep(_):
    pass


def sgweekend_session():
    return FakeSession({None: SGWEEKEND_LATEST, 3814: SGWEEKEND_BEFORE})


# ---- parsing one page -------------------------------------------------------------

def test_parses_posts_with_sgt_timestamps_and_emoji():
    records, oldest = _parse_page(SGWEEKEND_LATEST, "sgweekend")
    assert len(records) == 20 and oldest == 3814
    first = records[0]
    assert first["channel"] == "sgweekend"
    assert first["post_id"] == "sgweekend/3814"
    assert first["source_url"] == "https://t.me/sgweekend/3814"
    # the real post's footer <time> carries 2026-10-02T10:03:00+00:00 (UTC); SGT is +8h
    assert first["posted_at"] == "2026-10-02T18:03:00+08:00"
    assert "📝" in first["text"] and "✨" in first["text"]
    assert first["links"][0].startswith("https://tco.sg/")


def test_posts_are_returned_oldest_first():
    records, _ = _parse_page(SGWEEKEND_LATEST, "sgweekend")
    numbers = [post_number(r["post_id"]) for r in records]
    assert numbers == sorted(numbers)


def test_channel_casing_is_the_caller_s_not_telegram_s():
    # Telegram's own markup for this channel uses data-post="sgWhereTo/...", but we must
    # key posts the way config.LEPAK_CHANNELS and the rest of the pipeline spell it.
    assert 'data-post="sgWhereTo/' in SGWHERETO_LATEST
    records, _ = _parse_page(SGWHERETO_LATEST, "sgwhereto")
    assert len(records) == 15
    assert all(r["post_id"].startswith("sgwhereto/") for r in records)
    assert all(r["source_url"].startswith("https://t.me/sgwhereto/") for r in records)


def test_media_only_and_untimed_posts_are_skipped():
    html = """
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="sgweekend/1">
        <div class="tgme_widget_message_meta">
          <a class="tgme_widget_message_date" href="https://t.me/sgweekend/1">
            <time class="time" datetime="2026-01-01T00:00:00+00:00">08:00</time></a>
        </div>
      </div>
    </div>
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="sgweekend/2">
        <div class="tgme_widget_message_text js-message_text">No timestamp here</div>
      </div>
    </div>
    <div class="tgme_widget_message_wrap">
      <div class="tgme_widget_message" data-post="sgweekend/3">
        <div class="tgme_widget_message_text js-message_text">Real post<br/>with text</div>
        <div class="tgme_widget_message_meta">
          <a class="tgme_widget_message_date" href="https://t.me/sgweekend/3">
            <time class="time" datetime="2026-01-01T01:00:00+00:00">09:00</time></a>
        </div>
      </div>
    </div>
    """
    records, oldest = _parse_page(html, "sgweekend")
    assert oldest == 1                       # the media-only post still counts for paging
    assert [r["post_id"] for r in records] == ["sgweekend/3"]
    assert records[0]["text"] == "Real post\nwith text"


# ---- fetch_posts: cursor, pagination, limits ---------------------------------------

def test_no_cursor_or_limit_returns_one_page():
    session = sgweekend_session()
    records = fetch_posts("sgweekend", session=session, sleep=no_sleep)
    assert len(records) == 20
    assert session.calls == [None]           # no unnecessary pagination


def test_since_post_id_returns_only_newer_posts_and_paginates():
    session = sgweekend_session()
    records = fetch_posts("sgweekend", since_post_id="sgweekend/3800",
                          session=session, sleep=no_sleep)
    assert session.calls == [None, 3814]     # had to page back past the cursor
    assert all(post_number(r["post_id"]) > 3800 for r in records)
    assert records[0]["post_id"] == "sgweekend/3801"
    assert records[-1]["post_id"] == "sgweekend/3835"


def test_since_post_id_within_first_page_does_not_paginate():
    session = sgweekend_session()
    records = fetch_posts("sgweekend", since_post_id="sgweekend/3830",
                          session=session, sleep=no_sleep)
    assert session.calls == [None]
    assert [post_number(r["post_id"]) for r in records] == list(range(3831, 3836))


def test_limit_beyond_one_page_paginates_and_trims_to_most_recent():
    session = sgweekend_session()
    records = fetch_posts("sgweekend", limit=30, session=session, sleep=no_sleep)
    assert len(records) == 30
    assert session.calls == [None, 3814]
    assert records[-1]["post_id"] == "sgweekend/3835"


# ---- errors --------------------------------------------------------------------

def test_raises_http_error_after_retry_on_persistent_failure():
    session = FakeSession({None: SGWEEKEND_LATEST}, fail_times=2)
    with pytest.raises(HttpError):
        fetch_posts("sgweekend", session=session, sleep=no_sleep)


def test_recovers_after_one_transient_failure():
    session = FakeSession({None: SGWEEKEND_LATEST}, fail_times=1)
    records = fetch_posts("sgweekend", session=session, sleep=no_sleep)
    assert len(records) == 20
