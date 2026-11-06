"""Venue photos for event cards: which Wikipedia article counts as the venue, what the
card shows when none does, and how the offline build records its choices. No network:
Wikipedia lookups and downloads are stood in for. The venue names in the matching tests
are the ones gowhere/lepak/images.py says MATCH_THRESHOLD was tuned on."""
import json
import logging
import sqlite3

import pytest

from gowhere.adapters.http import HttpError
from gowhere.lepak import images
from gowhere.lepak.images import (VenueImages, best_match, image_credit, load_manifest,
                                  load_overrides, match_score, slugify)


def page(title, thumb="https://img/x.jpg"):
    return {"title": title, "pageimage": "x.jpg", "thumbnail": {"source": thumb}}


# ---- matching a venue to an article --------------------------------------------------

@pytest.mark.parametrize("text, slug", [
    ("Marina Bay Sands", "marina-bay-sands"),
    ("Esplanade – Theatres on the Bay", "esplanade-theatres-on-the-bay"),
    ("  Café  &  Bar!! ", "cafe-bar"),
    ("***", ""),
])
def test_slugify(text, slug):
    assert slugify(text) == slug


def test_an_exact_title_scores_one():
    assert match_score("Capitol Theatre", "Capitol Theatre") == 1.0


@pytest.mark.parametrize("venue, title", [
    ("Marina Bay Sands", "Marina Bay Sands"),
    ("Capitol Theatre", "Capitol Theatre"),
    ("Fort Canning Park", "Fort Canning Hill"),     # the tail renamed: still the venue
])
def test_the_right_article_is_accepted(venue, title):
    found, score = best_match(venue, [page(title)])
    assert found["title"] == title and score >= images.MATCH_THRESHOLD


@pytest.mark.parametrize("venue, title", [
    ("Singapore National Stadium", "Singapore National Eye Centre"),
    ("Esplanade Concert Hall", "Esplanade Bridge"),
])
def test_the_two_dangerous_near_misses_are_rejected(venue, title):
    found, score = best_match(venue, [page(title)])
    assert found is None and score < images.MATCH_THRESHOLD


def test_the_best_of_several_articles_wins():
    found, _ = best_match("Capitol Theatre", [page("Stamford House"), page("Capitol Theatre")])
    assert found["title"] == "Capitol Theatre"


def test_an_article_with_no_photo_cannot_be_chosen():
    without_photo = {"title": "Capitol Theatre"}
    assert best_match("Capitol Theatre", [without_photo]) == (None, 0.0)
    assert best_match("Capitol Theatre", []) == (None, 0.0)


# ---- the two files a person can edit or break ----------------------------------------

def test_overrides_are_keyed_by_slug_and_skip_rows_that_name_nothing(tmp_path):
    path = tmp_path / "venue_images.csv"
    path.write_text("venue,wikipedia_title,file\n"
                    "Esplanade Theatre,Esplanade,\n"
                    "Hand Made,,hand.jpg\n"
                    "Empty Row,,\n"
                    ",No Venue,\n", encoding="utf-8")
    assert set(load_overrides(path)) == {"esplanade-theatre", "hand-made"}


def test_no_overrides_file_is_not_an_error(tmp_path):
    assert load_overrides(tmp_path / "missing.csv") == {}


def test_no_manifest_is_not_an_error(tmp_path):
    assert load_manifest(tmp_path / "missing.json") == {}


def test_a_broken_manifest_falls_back_to_artwork_and_says_so(tmp_path, caplog):
    path = tmp_path / "manifest.json"
    path.write_text("{ not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        assert load_manifest(path) == {}
    assert "fall back to artwork" in caplog.text


# ---- what a card shows ---------------------------------------------------------------

RECORD = {"file": "esplanade.jpg", "title": "Esplanade", "credit": "A. Photographer",
          "licence": "CC BY-SA 4.0", "source_url": "https://en.wikipedia.org/wiki/Esplanade"}


def test_a_matched_venue_shows_its_photo_with_credit():
    shown = VenueImages({"esplanade-theatre": RECORD}).for_event("Esplanade Theatre", "Arts & Culture")
    assert shown["kind"] == "photo" and shown["path"] == "venues/esplanade.jpg"
    assert shown["credit"] == "A. Photographer" and shown["licence"] == "CC BY-SA 4.0"


def test_alt_text_names_the_building_when_it_is_not_the_venue():
    shown = VenueImages({"esplanade-theatre": RECORD}).for_event("Esplanade Theatre", "Arts & Culture")
    assert shown["alt"] == "Esplanade, the building housing Esplanade Theatre"
    shown = VenueImages({"esplanade": RECORD}).for_event("Esplanade", "Arts & Culture")
    assert shown["alt"] == "Esplanade"


@pytest.mark.parametrize("venue", ["Nowhere Hall", "", None])
def test_no_photo_means_category_artwork_never_a_blank_card(venue):
    shown = VenueImages({}).for_event(venue, "Arts & Culture")
    assert shown["kind"] == "artwork" and shown["path"] == "img/category/arts-culture.svg"
    assert shown["credit"] is None and shown["alt"] == "Arts & Culture event"


def test_the_artist_field_loses_its_html(monkeypatch):
    reply = {"query": {"pages": [{"imageinfo": [{"extmetadata": {
        "Artist": {"value": '<a href="/u/x">Jo  Tan</a>\n'},
        "LicenseShortName": {"value": "CC BY 2.0"}}}]}]}}
    monkeypatch.setattr(images, "get_json", lambda *a, **k: reply)
    assert image_credit(None, "x.jpg") == ("Jo Tan", "CC BY 2.0")


def test_a_file_with_no_metadata_still_gets_a_credit_line(monkeypatch):
    monkeypatch.setattr(images, "get_json", lambda *a, **k: {"query": {"pages": []}})
    assert image_credit(None, "x.jpg") == ("Unknown", "see Wikimedia Commons")


# ---- the offline build ---------------------------------------------------------------

class Wikipedia:
    """Stands in for the three calls build() makes. `nearby` is {lat: [pages]}."""

    def __init__(self, monkeypatch, nearby=(), titled=None, broken_download=False):
        self.nearby, self.titled = dict(nearby), titled or {}
        self.downloads, self.lookups = [], []
        self.broken_download = broken_download
        monkeypatch.setattr(images, "nearby_articles", self.nearby_articles)
        monkeypatch.setattr(images, "article_by_title", lambda s, title, l=None: self.titled.get(title))
        monkeypatch.setattr(images, "image_credit", lambda s, f, l=None: ("A. Photographer", "CC0"))
        monkeypatch.setattr(images, "_download", self.download)
        monkeypatch.setattr(images, "_normalise", lambda path: None)

    def nearby_articles(self, session, lat, lon, limiter=None):
        self.lookups.append(lat)
        return self.nearby.get(lat, [])

    def download(self, session, url, dest, limiter=None):
        if self.broken_download:
            raise HttpError("HTTP 503", status=503)
        self.downloads.append(dest.name)
        dest.write_bytes(b"photo")
        return 5


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """The build's files, moved under tmp_path so nothing touches the committed ones."""
    monkeypatch.setattr(images, "IMAGE_DIR", tmp_path / "venues")
    monkeypatch.setattr(images, "MANIFEST_PATH", tmp_path / "venues" / "manifest.json")
    monkeypatch.setattr(images, "OVERRIDES_PATH", tmp_path / "overrides.csv")
    # Their default paths were fixed when images.py was imported.
    monkeypatch.setattr(images, "load_manifest", lambda: load_manifest(images.MANIFEST_PATH))
    monkeypatch.setattr(images, "load_overrides", lambda: load_overrides(images.OVERRIDES_PATH))
    return tmp_path


def events_db(path, *venues):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE event (venue TEXT, lat REAL, lon REAL)")
    db.executemany("INSERT INTO event VALUES (?, ?, ?)", venues)
    db.commit()
    db.close()
    return path


def built(workspace):
    return json.loads((workspace / "venues" / "manifest.json").read_text(encoding="utf-8"))


def test_a_good_match_is_downloaded_and_recorded(workspace, monkeypatch):
    wiki = Wikipedia(monkeypatch, nearby={1.0: [page("Capitol Theatre")]})
    db = events_db(workspace / "e.db", ("Capitol Theatre", 1.0, 103.0))
    counts = images.build(events_path=db, session=object())
    assert counts["photo"] == 1 and wiki.downloads == ["capitol-theatre.jpg"]
    record = built(workspace)["capitol-theatre"]
    assert record["file"] == "capitol-theatre.jpg" and record["credit"] == "A. Photographer"
    assert record["source"] == "wikipedia" and record["match"] == 1.0


def test_a_near_miss_stays_artwork_and_is_not_recorded(workspace, monkeypatch):
    Wikipedia(monkeypatch, nearby={1.0: [page("Esplanade Bridge")]})
    db = events_db(workspace / "e.db", ("Esplanade Concert Hall", 1.0, 103.0))
    assert images.build(events_path=db, session=object())["artwork"] == 1
    assert built(workspace) == {}


def test_a_second_run_only_looks_up_new_venues(workspace, monkeypatch):
    wiki = Wikipedia(monkeypatch, nearby={1.0: [page("Capitol Theatre")]})
    db = events_db(workspace / "e.db", ("Capitol Theatre", 1.0, 103.0))
    images.build(events_path=db, session=object())
    wiki.lookups.clear()
    assert images.build(events_path=db, session=object())["kept"] == 1
    assert wiki.lookups == []


def test_refresh_looks_every_venue_up_again(workspace, monkeypatch):
    wiki = Wikipedia(monkeypatch, nearby={1.0: [page("Capitol Theatre")]})
    db = events_db(workspace / "e.db", ("Capitol Theatre", 1.0, 103.0))
    images.build(events_path=db, session=object())
    wiki.lookups.clear()
    assert images.build(events_path=db, refresh=True, session=object())["photo"] == 1
    assert wiki.lookups == [1.0]


def test_venues_in_one_building_share_one_file(workspace, monkeypatch):
    bay = page("Esplanade Hall")
    wiki = Wikipedia(monkeypatch, nearby={1.0: [bay], 2.0: [bay]})
    db = events_db(workspace / "e.db", ("Esplanade Hall", 1.0, 103.0), ("Esplanade Halls", 2.0, 103.0))
    assert images.build(events_path=db, session=object())["photo"] == 2
    assert wiki.downloads == ["esplanade-hall.jpg"]
    record = built(workspace)
    assert record["esplanade-hall"]["file"] == record["esplanade-halls"]["file"]


def test_an_override_beats_the_automatic_match(workspace, monkeypatch):
    (workspace / "overrides.csv").write_text("venue,wikipedia_title,file\n"
                                             "Esplanade Theatre,Esplanade,\n", encoding="utf-8")
    wiki = Wikipedia(monkeypatch, nearby={1.0: [page("Esplanade Theatre")]},
                     titled={"Esplanade": page("Esplanade")})
    db = events_db(workspace / "e.db", ("Esplanade Theatre", 1.0, 103.0))
    assert images.build(events_path=db, session=object())["override"] == 1
    assert wiki.lookups == []
    assert built(workspace)["esplanade-theatre"]["title"] == "Esplanade"


def test_an_override_file_is_used_without_any_lookup(workspace, monkeypatch):
    (workspace / "overrides.csv").write_text("venue,wikipedia_title,file,title\n"
                                             "Hand Made,,hand.jpg,Hand Made Hall\n", encoding="utf-8")
    wiki = Wikipedia(monkeypatch)
    db = events_db(workspace / "e.db", ("Hand Made", 1.0, 103.0))
    assert images.build(events_path=db, session=object())["override"] == 1
    assert wiki.lookups == [] and wiki.downloads == []
    assert built(workspace)["hand-made"]["file"] == "hand.jpg"


def test_a_failed_download_records_nothing_so_the_next_run_retries(workspace, monkeypatch):
    Wikipedia(monkeypatch, nearby={1.0: [page("Capitol Theatre")]}, broken_download=True)
    db = events_db(workspace / "e.db", ("Capitol Theatre", 1.0, 103.0))
    assert images.build(events_path=db, session=object())["failed"] == 1
    assert built(workspace) == {}


def test_a_failed_lookup_counts_as_failed_and_the_run_carries_on(workspace, monkeypatch):
    wiki = Wikipedia(monkeypatch, nearby={2.0: [page("Capitol Theatre")]})

    def flaky(session, lat, lon, limiter=None):
        if lat == 1.0:
            raise HttpError("HTTP 503", status=503)
        return wiki.nearby[lat]
    monkeypatch.setattr(images, "nearby_articles", flaky)
    db = events_db(workspace / "e.db", ("Lost Venue", 1.0, 103.0), ("Capitol Theatre", 2.0, 103.0))
    counts = images.build(events_path=db, session=object())
    assert counts["failed"] == 1 and counts["photo"] == 1


def test_blank_venues_are_skipped(workspace, monkeypatch):
    wiki = Wikipedia(monkeypatch)
    db = events_db(workspace / "e.db", ("   ", 1.0, 103.0), (None, 2.0, 103.0))
    images.build(events_path=db, session=object())
    assert wiki.lookups == [] and built(workspace) == {}
