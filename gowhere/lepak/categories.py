"""The eight event categories (DECISIONS.md section 11).

This one list drives the LLM's allowed values, the validator that discards anything
else, and the search form. They must never drift apart: a category the prompt allows
but the validator rejects would silently discard valid events.
"""
CATEGORIES = (
    "Food & Markets",
    "Arts & Culture",
    "Music & Performances",
    "Sports & Fitness",
    "Family & Kids",
    "Workshops & Classes",
    "Community",          # CC and RC activities: the most neighbourhood-bound events
    "Sales & Pop-ups",    # retail promotions, a large share of @sgwhereto's posts
)
# 1 to all 8 (DECISIONS.md section 32). The old cap of 4 assumed a wide search would
# flood the page; the first live ingestion held 38 events in total.
MIN_SELECTED, MAX_SELECTED = 1, len(CATEGORIES)
