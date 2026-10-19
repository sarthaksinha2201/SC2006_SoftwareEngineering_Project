"""Google ratings for a search's places, fetched at request time (DECISIONS.md 29).

Only places whose Google place ID was resolved offline (eat.db `google_place_id`) are
looked up. Each answer is accepted only if Google's name for the place matches ours,
because an IDs-only search can't be checked when it is made. A rating Google can't
supply, a name that doesn't match, a failed call and a spent daily cap all mean the
same thing to the user: no rating shown. A missing rating is never a low one.

Nothing is written anywhere. The ratings are attached to the user's own search results,
which live in that session's memory and expire with it (DECISIONS.md section 17).
"""
from concurrent.futures import ThreadPoolExecutor

from gowhere import config
from gowhere.eat.notable import own_name
from gowhere.lepak.images import match_score

NAME_MATCH = 0.5      # looser than the Wikipedia badge: Google adds branch names


def name_agrees(ours, theirs):
    if not theirs:
        return False
    return match_score(own_name(ours), own_name(theirs)) >= NAME_MATCH


def attach(results, adapter, workers=config.RATING_WORKERS):
    """Adds `rating` ({value, count, maps_url} or None) to each result. Returns the
    number of Google calls made."""
    wanted = [r for r in results if r.get("google_place_id")]
    for r in results:
        r["rating"] = None
    if not wanted or adapter is None or not adapter.configured:
        return 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        answers = list(pool.map(lambda r: adapter.details(r["google_place_id"]), wanted))
    for r, a in zip(wanted, answers):
        if a and a["rating"] is not None and name_agrees(r["name"], a["name"]):
            r["rating"] = {"value": a["rating"], "count": a["count"], "maps_url": a["maps_url"]}
    return sum(a is not None for a in answers)
