"""Where to Eat cuisine groups (DECISIONS.md sections 25 and 25a).

Eight user-facing groups, mapped from OSM `cuisine` values. "Local" replaces
Seafood (§25a). It holds the 123 hawker centres, the food courts and markets, venues
tagged `local`, `singaporean`, `noodle` and the like, and kopitiams found by name (see
is_kopitiam). Seafood would hold 133 venues.

`coffee_shop` is NOT a kopitiam marker, although it was first read as one: 646 venues
carry it, and they are Starbucks (144), Toast Box (79), Coffee Bean (78), Ya Kun (74),
Luckin (24) and other café chains. Only about 32 have kopitiam-style names. So it maps
to Cafés & Desserts.

A place can belong to several groups ("chinese;seafood"). A place whose tags map to no
group is "not listed": 45.9% of the 8,604 places in eat.db (19 Oct 2026), most of them
because OSM has no cuisine tag at all. These places are shown and labelled, never hidden
(§25).
"""
import re

CUISINES = (
    "Local",
    "Chinese",
    "Malay & Indonesian",
    "Indian",
    "Japanese & Korean",
    "Thai & Vietnamese",
    "Western",
    "Cafés & Desserts",
)
NOT_LISTED = "Cuisine not listed"

_TAGS = {
    "Local": "local singaporean regional hawker zi_char economic_rice "
                      "chicken_rice noodle noodles asian kopitiam laksa",
    "Chinese": "chinese cantonese hongkong taiwanese hotpot hot_pot dim_sum teochew hainanese "
               "szechuan sichuan shanghai dumpling dumplings peking_duck hakka hokkien",
    "Malay & Indonesian": "malay malaysian indonesian nasi_lemak padang peranakan nyonya",
    "Indian": "indian curry north_indian south_indian biryani pakistani prata sri_lankan "
              "nepalese bangladeshi",
    "Japanese & Korean": "japanese korean sushi ramen beef_bowl teppanyaki udon yakiniku "
                         "yakitori donburi tonkatsu izakaya",
    "Thai & Vietnamese": "thai vietnamese",
    "Western": "western burger pizza italian french american steak_house mexican pasta "
               "sandwich grill fish_and_chips spanish mediterranean european german greek "
               "british",       # not "seafood": here that is as often Chinese as Western
    "Cafés & Desserts": "dessert ice_cream cake bubble_tea juice donut tea coffee coffee_shop "
                        "bakery waffle crepe frozen_yogurt",
}
TAG_GROUP = {tag: group for group, tags in _TAGS.items() for tag in tags.split()}


_KOPITIAM = re.compile(r"kopitiam|eating house|coffee ?shop\b|food house|kopi tiam", re.I)


def is_kopitiam(name):
    """A kopitiam or eating house, judged by its name. OSM tags these inconsistently
    (as cafe, restaurant or food_court), so the name is the better evidence."""
    return bool(_KOPITIAM.search(name or ""))


def groups_for(cuisine_tag):
    """The groups an OSM `cuisine` value maps to, in CUISINES order ([] if none)."""
    tags = {t.strip().lower() for t in (cuisine_tag or "").split(";") if t.strip()}
    found = {TAG_GROUP[t] for t in tags if t in TAG_GROUP}
    return [c for c in CUISINES if c in found]
