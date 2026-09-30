# Where to Lepak: event ingestion

`python -m gowhere.ingest.run` turns channel posts into stored events:

```
posts (S2 contract, newer than the channel's marker)
  -> regex pre-filter          no date-like text: never sent to the LLM
  -> LLM extraction            batches of 10, claude-haiku-4-5, forced tool call
  -> validation                every field; failures discarded with a reason
  -> venue placement           OneMap search via LocationService; unplaced: discarded
  -> merge and store           data/events.db, then the channel's marker moves
  -> purge                     events that have ended are deleted, every run
```

| Command | What it does |
|---|---|
| `python -m gowhere.ingest.run` | One run now (the demo-day command) |
| `python -m gowhere.ingest.run --every-hours 6` | Keep running on the always-on host |
| `python -m gowhere.ingest.run --posts-file F` | Read post records from a file instead of the scraper |
| `python -m gowhere.ingest.run --report` | Yield of the recent runs |

Needs `ANTHROPIC_API_KEY` in `.env`. Without it every LLM call fails and nothing moves.
That is the designed failure path, not a crash.

## The rules

**Pre-filter.** A post goes to the LLM only if it contains date-like text: a day and month,
a numeric date, a weekday, or words such as "tonight" or "now till". The filter is meant
to be generous: a false positive costs a little of one call, while a false negative loses
events.

**Extraction.** The model can answer only through the `record_events` tool. Its schema
lists these fields for each event:

- post number
- title
- category (an enum of the eight categories)
- start
- end or null
- venue or null
- address or null
- summary

A post can yield zero, one or several events. A post listing several venues gives one
event per venue. The source link does not come from the model: each event names its post
by number within the batch, and the link is copied from that post. So the model can never
invent a link or point one elsewhere.

**Prompt injection.** The following measures apply:

- The system prompt says post text is untrusted data, never instructions.
- Each post is fenced in `<post>` tags, and its own angle brackets are replaced so it
  cannot close the fence early.
- The model's reply is never trusted. `test_a_model_that_obeys_the_post_still_cannot_store_its_demands`
  simulates the worst case, a model that obeys the post. The injected category, the
  forged link, the reference to a non-existent post and the 2099 date are all discarded.

**Validation** (`gowhere/ingest/extract.py`). An event is discarded, with a reason, when:

- the reply is malformed;
- it names a post that was not in the batch;
- the title is missing;
- the category is not one of the eight;
- the start date is missing;
- a date is not in the expected format, or does not exist;
- it ends before it starts;
- both venue and address are missing;
- the date is more than 400 days from the post's date;
- it has already ended.

A date with no time is all day, following DECISIONS §3. An event with no end is kept
until the end of its start day. Text fields are cleaned to plain single lines and length
capped.

**Venue placement** (`gowhere/services/location.py`, `match_place`). Candidate queries
are tried in this order:

1. a 6-digit postal code, if the post gives one;
2. the venue name;
3. each comma-separated part of the address;
4. the venue name with trailing words dropped, down to 2 words ("Marina Bay Sands
   Convention Centre" becomes "Marina Bay Sands").

Unit numbers, floors and halls are removed from the text first.

A result is accepted only if the whole query appears word for word in its name or street
address. A one-word query must match a name exactly. Several matches are accepted only if
they are the same place: within 300 m of each other, or all sharing one postal code.

Two venues in the fixtures show why the rule is this strict:

- "Tampines 1" would otherwise have been placed on Tampines Avenue 1.
- OneMap has no "Capitol Singapore", only "Eden Residences Capitol".

Both are discarded and logged rather than placed somewhere wrong. OneMap's venue answers
are public, so they use the on-disk search cache. A user's own postal code
(`LocationService.postal`) stays in memory only.

**Duplicates.** Two events are one event when all of these hold:

- they start on the same date;
- their titles are similar: half the significant words are shared, or one title's words
  all appear in the other;
- they are within 200 m of each other.

The first stored copy keeps its fields and gains the second copy's source link. A field
the first copy lacks is filled from the second, and the later end is kept. Reprocessing
the same post merges into itself, so no duplicate is created.

**The marker.** Posts are processed oldest first. A channel's `last_post_id` moves past a
post only once its batch's events are committed, and the events and marker are written in
one transaction. If the LLM call or OneMap fails, the run stops for that channel. The
posts are then retried next run, never skipped. The test compares a failed run followed by
a catch-up run against a clean run, and finds the same events: none lost, none doubled.

**What is stored.** `event` has only extracted fields, OneMap's matched place name,
coordinates and timestamps. `event_source` holds the links. There is no post text, no
channel member and no poster. Tests dump the database and the log, and check that no line
of any post's text appears in either. Log lines carry post ids, extracted titles and
discard reasons.

## Fixture run

The fixture is 31 real posts, saved 30 Sep 2026: 20 from @sgweekend and 11 from
@sgwhereto. They are run as of 30 Sep 2026 12:00.

| Stage | Count |
|---|---|
| Posts | 31 |
| Pre-filtered out, no date-like text (4 deals, 1 list) | 5 |
| Sent to the LLM | 26 |
| Posts with no events (lists, giveaways) | 5 |
| Events extracted | 32 |
| Discarded: already ended | 15 |
| Discarded: missing location (online shop, "all stores", no venue given) | 4 |
| Discarded: venue could not be placed | 2 |
| **Stored** | **11** |

"Already ended" dominates only because the fixture posts are up to three weeks old. A live
6-hourly run sees mostly new posts.

**Caveat:** the LLM replies in `tests/fixtures/lepak/extractions.json` are hand-written to
the extraction rules, not recorded from Haiku, because there is no API key yet. The
pipeline, validator, placement, merge and marker are tested; the model's own accuracy is
not. Once a key exists:

1. Run the command above on `posts.json` with the real model.
2. Diff the result against the stand-in.
3. Replace the stand-in with the real replies.

The tool is sent with `strict: true`. If the API rejects the schema under strict mode,
every call fails loudly with the API's message, and removing that flag is the fix.

## Interfaces assumed

- **S2 scraper:** `gowhere.ingest.telegram.fetch_posts(channel, since_post_id="sgweekend/1234")`,
  returning post records oldest first. Sarthak.md fixes the record shape but not the
  function name. `TelegramPostSource` is the one place to adjust.
- **Event store:** `data/events.db`, a file separate from `snapshot.db`. The snapshot is
  replaced wholesale on every rebuild (temp file, validate, swap), which would wipe events
  kept in the same file.
