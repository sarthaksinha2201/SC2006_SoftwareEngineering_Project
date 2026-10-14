# Where to Lepak: event ingestion

`python -m gowhere.ingest.run` turns channel posts into stored events:

```
posts (S2 contract, newer than the channel's marker)
  -> regex pre-filter          no date-like text: never sent to the LLM
  -> LLM extraction            batches of 10, OpenAI gpt-6-luna, strict JSON schema
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

Needs `OPENAI_API_KEY` in `.env`. Without it every LLM call fails and nothing moves.
That is the designed failure path, not a crash.

## The LLM adapter

`gowhere.adapters.llm.LlmAdapter` is the only code that knows which provider is used.
The pipeline calls `call_tool(system, user, tool)` and gets back a dict shaped by the
tool's schema.

- **Provider and model:** OpenAI's Responses API with `gpt-6-luna`, OpenAI's model for
  high-volume tasks. On 14 Oct 2026 it cost US$0.10 per million input tokens and
  US$0.50 per million output tokens. It is a reasoning model, and reasoning tokens are
  billed as output, so `config.LLM_REASONING_EFFORT` is `low`.
- **Structured Outputs:** the `record_events` schema is sent as a strict JSON schema, so
  the API rejects any reply that does not fit it. `extract.validate` still checks every
  field. It is the second line of defence, and the one that stops a post persuading the
  model to put a made-up value in a valid field.
- **Privacy:** `store=False`, so OpenAI keeps no copy of the posts.
- **The key** is never in an error or a log line. Error text is scrubbed of the key, and
  of anything shaped like one, before it leaves the adapter. The SDK's exception is not
  chained, because it can carry the request headers. `tests/test_llm_adapter.py`
  checks this.
- **Cost:** every call logs its token counts, and the adapter keeps running totals
  (`usage`, `cost_usd()`).

The provider was switched from Anthropic to OpenAI on 14 Oct 2026, because that is the key
the team has. The switch changed the adapter class, its own tests, the model constant
and the dependency. Nothing else in the pipeline changed.

## What the first real run discarded, and why (14 Oct 2026)

The first run extracted 140 events and stored 28 (docs/demo.md section 4). To find out
whether the two largest addressable buckets were our fault or genuine, we re-fetched the
posts behind them and re-extracted them with the same model and prompt. The batches
differed and the model is not deterministic, so this reproduces the discards rather
than replaying them exactly. It cost US$0.004.

**Venue not placed (21): mostly our matcher, partly fixed.** The model's venue strings
were good. Eleven of the 21 discards, which were 10 distinct events because one was
extracted twice, were well-known places that OneMap knows under another name or that our
strict matcher rejects:

| Venue the model gave | Why it failed | Now |
|---|---|---|
| Suntec Convention Centre | OneMap: "Suntec Singapore Convention & Exhibition Centre"; not a contiguous match | alias 039593 |
| Great World | Partial hits on the mall, the MRT station and its exits, too far apart to be one place | alias 237994 |
| Fort Canning Park | Two exact hits, no postal code, too far apart | alias 179620 (Fort Canning Centre) |
| Esplanade Recital Studio, Esplanade Annexe Studio | No OneMap result | alias 038981 |
| Isetan Scotts | No OneMap result; the store is in Shaw House | alias 238868 |
| Clarke Quay Central | No OneMap result; OneMap calls it The Central | alias 059817 |
| F1 Pit Building | No OneMap result; OneMap calls it The Pit Building | alias 038975 |
| KC Arts Centre | No OneMap result; it is SRT's home at 20 Merbau Road | alias 239035 |
| SKAI (address "Swissôtel The Stamford") | OneMap does not match the accented name | alias 178882 |

Each alias has its source in `data/reference/venue_aliases.csv`. The other nine are small
galleries and studios named with no address: The Private Museum, IMBA, Supper House,
Fever Exhibition Hall, Heartware Store & Gallery, The Fluxus House, Whitestone Gallery,
Shop—House by DECK and Gravity by Noir. RASA Space, a club, stays unplaced too. Guessing
their locations is exactly what the matcher exists to prevent. A matcher rule for
parks was considered and rejected: it would recover about one event at the cost of a
special case in the matching rules, and the alias file already covers such venues with
a source for each (DECISIONS §20).

**Recovery run (14 Oct, 23:27 SGT):** the posts behind the 21 discards went back through
the real pipeline with the aliases in place. That run is recorded in `ingest_run` like
any other. All 10 recoverable events were stored; 10 venues stayed unplaced and 3 items
had no single venue. It took 6 calls, 7,373 input tokens (5,494 cached) and 3,041 output
tokens, US$0.0018. Channel markers only ever move forward, so re-processing older posts
cannot move them back. **events.db now holds 38 events.**

The discard log now records the venue and address the model gave, not just the title,
so the next unplaced venue can be judged from the log without re-running anything.

**No single venue (38): genuine, prompt unchanged.** The question was whether the prompt
makes the model collapse a roundup into one event with no venue. It does not. The model
splits each roundup into one event per item. Where an item names a place, the model
fills the venue in itself (MacRitchie Reservoir Park, Coney Island Park, Resorts World
Sentosa, Marina Bay Sands). The discarded items name no place in the text:

- "Free Workouts & Runs to Join This Weekend" lists give names and dates only; the
  details are behind links.
- F1 pop-up and appearance lists give brand names and dates only.
- Chain-wide deals say "All outlets" or "All Donki Bars".

We measured the limit of the source material and left it alone. A prompt change could
only make the model guess, which is exactly the wrong-venue failure the strict matcher
exists to prevent.

**Already ended (53)** is expected on a first run, which reads posts up to a few weeks
old. Later runs read only new posts.

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

**Venue placement** (`gowhere/services/location.py`, `match_place`). Lookups are tried in
this order:

1. **The alias list**, `data/reference/venue_aliases.csv` (DECISIONS §12). It holds venue
   names that OneMap doesn't know, each mapped to a postal code, with a source and the
   date it was checked. An alias matches the whole venue name after normalisation, never
   part of one. The list is filled by hand from the discard log, following the same
   pattern as the polyclinic and hospital lists, so every match stays auditable.
2. A 6-digit postal code, if the post gives one.
3. The venue name.
4. Each comma-separated part of the address.
5. The venue name with trailing words dropped, down to 2 words ("Marina Bay Sands
   Convention Centre" becomes "Marina Bay Sands").

Unit numbers, floors and halls are removed from the text first.

A OneMap result is accepted only if the whole query appears word for word in its name or
street address. A one-word query must match a name exactly. Several matches are accepted
only if they are the same place: within 300 m of each other, or all sharing one postal
code.

The alias list is seeded with the two venues the strict rule rejected in the fixtures:

- "Tampines 1" would otherwise have been placed on Tampines Avenue 1. Its alias points to
  Tampines One, postal code 529536.
- OneMap has no "Capitol Singapore", only "Eden Residences Capitol" and "Capitol Piazza".
  Its alias points to postal code 178905.

The rule itself stays strict: a wrong venue sends a user somewhere with a confident travel
time attached, while a missing one is only a gap. Measured cost without aliases: 2 of the
13 events still running were discarded. OneMap's venue answers are public, so they use the
on-disk search cache. A user's own postal code (`LocationService.postal`) stays in memory
only.

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
| Discarded: venue could not be placed | 0 (2 without the alias list) |
| **Stored** | **13** |

"Already ended" dominates only because the fixture posts are up to three weeks old. A live
6-hourly run sees mostly new posts.

**Caveat:** the LLM replies in `tests/fixtures/lepak/extractions.json` are hand-written to
the extraction rules, not recorded from the model, because there is no API key yet. The
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
