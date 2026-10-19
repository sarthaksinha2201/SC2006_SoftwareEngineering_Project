# GoWhere — Decision Log

SC2006 Team 5. Every decision with the reasoning behind it, for the final report and the QnA.
Last updated: 30 Sep 2026.

---

## 1. Scope and naming

**Decision:** App name is **GoWhere**; the two features are **Where to Live** and **Where to Lepak**.
**Reason:** Singlish phrasing fits the audience, and both names describe a question a real user asks.

**Decision:** Build two features, not three.
**Reason:** They share one backend (location → what's nearby → how to get there), so the second feature costs far less than it looks. A third would not fit 5 weeks with 2 people.

**Decision:** "Where to Eat" is documented as future work, not built.
**Reason:** Named in the report to show the design extends cleanly, without being graded on something unfinished.

**Decision:** A neighbourhood is a **URA Planning Area containing at least one HDB residential block**. *(Threshold under review — see below.)*
**Reason:** An authoritative government boundary means we never have to argue about what counts as a neighbourhood. The HDB-block rule automatically excludes reservoirs and industrial areas, using a dataset we already load — no extra population dataset needed.

**Decision:** **No minimum size threshold** — every planning area with at least one HDB residential block stays selectable and stays in the percentile baseline. *(Settled 30 Sep, after considering and rejecting a ≥1,000 dwelling-unit minimum.)*
**Reason:** A minimum was proposed because a near-empty area such as Changi occupies a full percentile rank (~0.3 points across ~35 areas) on the strength of a handful of Changi Village blocks. But people do choose to live there — a student at SUTD wanting quiet and cheaper rent is a real user — and excluding it would be the system deciding for them. A ~0.3-point baseline shift is a small price for not deleting a legitimate option.

**Decision:** Instead, **flag small areas in the results**: e.g. "Changi — 412 flats across 4 blocks. Scores are based on a small number of blocks."
**Reason:** The real weakness of a tiny area is that its median and P90 are computed over very few blocks and are therefore noisy. A label tells the user that directly, which serves the Transparency NFR better than silently removing the area.

**Decision:** The small-area note triggers below **10 HDB blocks**, flagging exactly **Changi (3 blocks / 166 flats), Tanglin (2 / 166) and Downtown Core (2 / 240)**. *(Set 30 Sep from the measured distribution.)*
**Reason:** Block counts have a clean gap — 2, 2, 3, then 25, 35, 42 and upwards — so any threshold between 4 and 25 flags the same three areas. 10 sits safely in the middle of that gap. A threshold of 30 would also catch Bukit Timah (25 blocks), which has enough blocks to be stable and should not be flagged.

**Decision:** The note is worded neutrally, because two of the three flagged areas score **high**, not low (Tanglin 9.4 and Downtown Core 9.1, each being 2 blocks beside a station; Changi 0.1).
**Reason:** The caveat is about sample size, not quality. Wording it as a warning about poor data would mislead in the two cases where a tiny sample produces a top-of-table score.

**Decision:** Scope facts for the report: **32 of 55 planning areas in scope; 10,796 residential blocks of 13,357; 1,175,956 dwelling units; 100% geocoded and placed.**
**Reason:** These are the numbers a grader will ask for, and the percentile denominator (n = 32) depends on the first one.

**Decision:** The report states **which areas fall below the small-area threshold** as a named limitation, once the per-area counts are known.
**Reason:** If it turns out to be Changi alone, the limitation is one sentence and easy to defend. If several areas qualify, that is worth knowing before the demo, because a grader asking "how reliable is this score?" should get a specific answer rather than a general one.

**Decision:** The factor is named **Public Transport** everywhere — documents, UI, and code.
**Reason:** "Transport" reads as though it might include driving. "Public Transport" says what is actually measured: walking access to MRT/LRT and buses.

**Decision:** No user accounts.
**Reason:** Nothing personal is stored, so there is nothing to protect. Personalisation comes from inputs held only for the session.

## 2. Where to Live — scoring

**Decision:** Six factors — public transport, housing affordability, amenities, greenery, healthcare, commute.
**Reason:** Covers what people actually weigh up when choosing where to live. Commute is the most personal of them.

**Decision:** Each factor can be **included or excluded**; included factors carry a weight of **1–10** (default 5).
**Reason:** Exclude is the only way to switch a factor off, so a weight of 0 doesn't duplicate it. A user with no fixed workplace excludes commute rather than faking a low weight.

**Decision:** Accessibility is measured **per HDB block and flat-weighted**, not counted per area.
**Reason:** Answers the tutor's Tampines objection directly. A large area with four MRT stations can still leave many flats far from one. Counting stations measures supply; measuring distance from homes measures access.

**Decision:** Report both **median and P90** walking distance.
**Reason:** P90 is the "unlucky resident" the tutor described. A median on its own hides a bad tail.

**Decision:** Category scores use **percentile rank** across in-scope areas, scaled 0–10.
**Reason:** Scores are stable (an area's score doesn't shift based on who it's compared with), the full 0–10 range is always used, and single extreme areas can't squash everyone else. The cost is that magnitude is discarded — we measure rank, not absolute quantity. Stated as an assumption.

**Decision:** **Average rank for ties**, and percentile computed only among areas that have data for that factor.
**Reason:** Amenities are capped at 3 per type, so many areas tie exactly. Without a tie rule, the Accuracy NFR cannot be met.

**Decision:** Overall score is the **weighted mean**, `Σ(score × weight) ÷ Σ(weight)`.
**Reason:** Keeps the result on 0–10 and directly comparable to category scores. All-5s and all-10s express the same preferences and must produce the same ranking — a plain weighted sum would triple the number instead.

**Decision:** Housing affordability = **% of matching resale transactions within the user's budget, ÷ 10**.
**Reason:** Personal to this user rather than a generic median, and fixing the flat type means we aren't comparing 3-room stock against 5-room stock.

**Decision:** Housing data is treated as unavailable below **10 matching transactions**.
**Reason:** Below that, a percentage is noise.

**Decision:** Missing data → **drop that factor for all selected areas** and tell the user.
**Reason:** Every area stays scored on identical criteria. Scoring areas on different factor sets would make the ranking meaningless.

**Decision:** Commute uses an **absolute scale** (≤20 min → 10, ≥80 min → 0, linear between).
**Reason:** It depends on the user's destination, so it can't be precomputed. Percentile rank would require routing for all ~30 areas on every request.

**Decision:** Commute is measured from **one representative block per area** — the HDB block nearest the area's flat-weighted centroid. *(Revised 30 Sep; was 5 sample blocks.)*
**Reason:** Cuts routing from 20 calls per comparison to at most 4, and the accuracy loss is small *for this factor specifically*. On a 45-minute commute, which block you start from changes the total by a few minutes; on a 10-minute walk to the MRT, the block is the entire measurement. That's why block-level detail is kept for walking access and dropped for commute. Using the nearest real block rather than the bare centroid guarantees a routable address.

**Decision:** A tie is equality at **1 decimal place**, and produces a joint rank.
**Reason:** With floating-point scores, exact ties never occur, so the joint-rank requirement would otherwise be unreachable code.

**Decision:** The explanation ranks factors by **marginal contribution**, `(winner − runner-up) × weight`.
**Reason:** Ranking by score × weight just replays the user's own biggest slider back at them and says the same thing regardless of which area won. Marginal contribution answers "why this one instead of that one".

**Decision:** Warn when the top two differ by **0.2 or less**.
**Reason:** Honest about a result that a single slider would flip. Supports the Transparency NFR.

**Decision:** Compare **2–4** neighbourhoods.
**Reason:** The chart stays readable and the commute routing budget stays small.

### 2a. Exact definitions (added 30 Sep, from ETL implementation)

These were needed to make the golden test reproducible. None changes the design; they pin down wording that was ambiguous.

**Decision:** Transport category score = `0.7 × percentile rank of (% of flats within a 10-minute walk) + 0.3 × percentile rank of (median walking time)`. **P90 is displayed to the user but does not enter the score.**
**Reason:** The score should reward the typical resident; P90 is shown so the user can see the spread for themselves rather than having it silently folded into one number.

**Decision:** Percentile rank = `(average_rank − 1) ÷ (n − 1) × 10`, where rank 1 is the worst-performing area. Ties are exact equality of the raw value. With one area, the score is 10.
**Reason:** Average rank is the standard convention for ties. Defining ties on the raw value rather than the rounded score avoids two areas tying only because of display rounding.

**Decision:** Weighted median and P90 are the **inverse CDF with no interpolation** — the first value at which cumulative flats ≥ q × total flats.
**Reason:** Reproducible by hand, which the Accuracy NFR requires. Worked example: blocks of 100 and 100 flats at 5 and 15 minutes → median is 5, not 10.

**Decision:** "Within a 10-minute walk" is **inclusive** (≤ 10.0 minutes).
**Reason:** A boundary that isn't written down is a boundary two people will implement differently — and it's a black-box test case.

**Decision:** All displayed scores use **half-up rounding** (`round1`), not Python's built-in `round()`. The 1-decimal-place joint-rank tie rule uses the same function.
**Reason:** Python uses banker's rounding, so `round(8.25, 1)` gives 8.2 while a hand calculation gives 8.3. Any score landing on `.x5` would fail the Accuracy NFR ("manual recalculation must match to 1 decimal place") — the NFR would be violated by the rounding function alone, with the scoring logic entirely correct.

**Decision:** Only exact block-number + road-name matches are accepted when geocoding; every failure is logged with OneMap's candidate matches rather than silently dropped.
**Reason:** A wrong geocode moves a block to the wrong neighbourhood and corrupts that area's score invisibly. A logged failure is a known gap; a wrong match is a wrong answer.

## 3. Where to Lepak — events

**Decision:** The event source is **public Telegram channels**.
**Reason:** STB's Tourism Information Hub — the obvious government events API — was discontinued on 31 July 2025. No official events feed exists.

**Decision:** Read channels through the **public web view `t.me/s/<channel>`**, not the Telegram API.
**Reason:** Static HTML, so `requests` + BeautifulSoup is enough. No API credential, no phone-number registration, no account that can be restricted. The Telegram client library stays documented as a fallback.

**Decision:** Rejected **Reddit scraping with Puppeteer**.
**Reason:** Measured on t.me/s/sgweekend: ~4–5 posts/week, and 13 of the last 15 posts carried both a date and a named venue (~87% usable). Reddit is discussion rather than listings, so yield is far lower, and it needs a headless browser inside a Python project. Worse data for more infrastructure.

**Decision:** Channels must be **broadcast channels, not group chats**, and must have the `t.me/s/` web view enabled.
**Reason:** Group chats are real people talking — storing that raises PDPA problems and breaks our own Security NFR. Groups also don't expose a readable post feed, so the approach wouldn't work anyway. (This is why @sgnightlife was rejected: 20k-member group, no visible feed.)

**Decision:** **LLM extraction** into a fixed schema, not regex parsing.
**Reason:** Posts are free text with emoji, inconsistent date formats, and often several events in one post. Regex would be brittle and miss most of them.

**Decision:** The LLM **extracts only and never follows instructions found in post text**.
**Reason:** Post text is untrusted public input, so this is prompt injection. Output is validated against the schema before storage and escaped on display. Feeds the course's Dependability and Security section.

**Decision:** Store **only extracted fields plus the source link** — never raw message text or poster identity.
**Reason:** PDPA, and it keeps the Security NFR ("no personally identifiable information") literally true.

**Decision:** Ingest **every 6 hours**, not hourly.
**Reason:** Cost is driven by post volume, not frequency — only unseen posts are processed, so hourly and 6-hourly cost nearly the same. 6-hourly is chosen for simpler operation. A manual run is available before the demo. *(Measured 14 Oct: US$0.0100 for a full run across 7 channels, about US$0.04/day at 4 runs. See §19.)*

**Decision:** **Regex pre-filter**, then **batch ~10 posts per LLM call**.
**Reason:** Posts with no date-like text never reach the LLM, and batching avoids re-sending the instruction prompt for every post.

**Decision:** An event with a date but **no time is treated as all-day**.
**Reason:** Over half the posts in a good channel give a date and no time. Discarding them would throw away most of the feed.

**Decision:** **Discard** events whose venue cannot be geocoded; log every failure.
**Reason:** An event that can't be placed on a map or routed to is useless in this feature. Logging makes the geocoding hit rate visible rather than silent.

**Decision:** Results are **sorted, not scored**.
**Reason:** A second scoring formula would add documentation and testing work without helping someone choose an event for this weekend.

**Decision:** Sort options are soonest / shortest travel time / recently added. **No price.**
**Reason:** Telegram posts rarely state a price, so a price sort would be mostly empty.

**Decision:** **No separate filter panel** — the search form already filters; the results page has sort plus category chips.
**Reason:** Fewer controls doing the same job. Supports the Usability NFR.

**Decision:** Route at most **50 events** per search.
**Reason:** Caps external API calls and keeps the 8-second performance target reachable.

## 4. Architecture

**Decision:** A **responsive web app**, not a mobile app.
**Reason:** Two people, five weeks. A phone browser already provides device location, so Lepak works on a phone without an Android toolchain or a second language.

**Decision:** **Flask + SQLite + Jinja**, with Leaflet for maps and Chart.js for charts.
**Reason:** Flask stays out of the way of the hand-drawn class diagram we're graded on, where Django's conventions would fight it.

**Decision:** **Two SQLite files, not one**: `data/snapshot.db` (neighbourhood data) and `data/events.db` (Lepak events). *(Corrected 30 Sep; an earlier line said one file.)*
**Reason:** A snapshot rebuild replaces the whole file, which would wipe every stored event. The two have different lifecycles — the snapshot is regenerated wholesale every few months, events accumulate every 6 hours — so they cannot share a file.

**Decision:** **Two-tier data** — a static snapshot from the offline ETL, plus an event store from scheduled ingestion.
**Reason:** Different lifecycles: the snapshot changes yearly, events change daily. It also gives the architecture diagram a clean subsystem split.

**Decision:** The web app **never calls a bulk Data Source at runtime** — data.gov.sg, OpenStreetMap and LTA's static datasets are read only by the offline ETL. *(Wording clarified 30 Sep.)*
**Reason:** The demo cannot fail because data.gov.sg is slow. Makes the Performance and Reliability NFRs achievable by construction.

**Decision:** **External Services are different from Data Sources** and are called at request time by design: OneMap routing (commute, and travel time in Where to Lepak) and LTA DataMall carpark availability.
**Reason:** Neither can be precomputed — a route depends on the user's own destination, and carpark availability is only meaningful live. Each is reached through its own adapter with a documented fallback (commute treated as unavailable; parking shown as unavailable), so a failure degrades one factor rather than the page.

**Decision:** The active snapshot is replaced **only after validation passes**.
**Reason:** A failed refresh leaves the previous snapshot active, so the app is never left without data.

**Decision:** App and scheduler run on **one always-on host**.
**Reason:** Two deployments is twice the operations work for a 5-week project. `python -m etl.ingest` stays runnable locally as the demo-day fallback.

**Decision:** **Strategy** pattern for the six factors.
**Reason:** Directly implements the Supportability NFR — a new factor is a new class with no change to the scoring engine. The pattern *proves* the NFR instead of just asserting it.

**Decision:** **Adapter** per external service (OneMap, LTA DataMall, Telegram, LLM).
**Reason:** Makes them mockable, which the test plan depends on.

**Decision:** **Facade** for the shared services (LocationService, RouteService).
**Reason:** Both features call the same operations; the facade is what the "Shared Services" package in the use case diagram becomes in code.

**Decision:** Walking time = **straight-line distance × detour factor ÷ 80 m per minute**.
**Reason:** Real walking routes for all 10,796 residential blocks would be far too many API calls — the existing prototype does exactly that per location and cannot scale. Straight-line distance is pure arithmetic from two coordinates, so it costs nothing; the detour factor converts it into a realistic walking distance.

**Decision:** The detour factor is **1.39**, the measured median. *(Calibrated 30 Sep; replaced the 1.3 placeholder, which came from the 1.2–1.4 range commonly cited for street-network circuity.)*
**Reason:** Measured over 200 blocks stratified by flat share, all 200 routes succeeding. Median 1.39, IQR 1.29–1.57, P10–P90 1.22–1.86. The placeholder 1.3 sat at about the 25th percentile, so it was systematically optimistic — **73% of sampled blocks walk further than 1.3 assumes**. Adopting 1.39 improves agreement with the real route on the "within 10 minutes" verdict from 89.5% to 93.0% and cuts mean absolute error from 1.6 to 1.4 minutes. That matters because the percentage of flats within a 10-minute walk is a number shown directly to the user. The ratio is also flat across distance bands (1.39 / 1.39 / 1.37 / 1.36 for 0–400 / 400–800 / 800–1200 / 1200+ m), which confirms a single multiplicative factor is the right model shape rather than a distance-dependent one. OneMap's own implied walking speed of 83 m/min independently supports our 80 m/min assumption.

**Decision:** The rule for replacing the factor is **"adopt the measured median when it improves 10-minute agreement by ≥1 percentage point"**, not "when it differs by more than an arbitrary band".
**Reason:** An earlier ±0.1 tolerance would have kept 1.3 while hiding a 3.5-point accuracy difference in the figure users read. The threshold should be tied to what the score actually uses.

**Decision:** Adopting 1.39 was checked against the rankings before acceptance.
**Reason:** Scaling every walk by the same constant cannot change the median-walk percentile ranks, since order is preserved; only the "% within 10 minutes" figure moves (down 1–6 points per area). No score moved by more than 0.45, the top 18 and bottom 4 areas were identical, and 9 middle-band areas swapped by at most 2 places. So the change buys accuracy in a displayed number without destabilising the recommendation.

**Decision:** Per-area detour medians (1.31 Bedok to 1.70 Hougang) are reported as a **limitation**, not implemented.
**Reason:** A 0.39 spread is real, but with only 5–15 sampled blocks per area those medians are indicative, not reliable. Per-area factors are named as future work.

**Decision:** Calibrate against **200 sampled blocks**, drawn in proportion to each area's share of dwelling units, and take the **median** ratio.
**Reason:** Three things set the number.
*Precision:* the standard error of a sample median is about `1.25 σ/√n`. With the spread we expect in walking ratios, n = 200 gives roughly ±0.06 on the factor — about half a minute of walking error at typical distances, which is well inside the resolution of a 10-minute threshold.
*Diminishing returns:* halving to 100 blocks nearly doubles the error; doubling to 400 improves it only ~30%. 200 is where the curve flattens.
*Cost:* 200 routing calls take a few minutes, against 10,796 for the exhaustive version — a ~2% sample for ~2% of the cost.
The median rather than the mean, because blocks separated from their station by an expressway or canal sit in a long upper tail (ratios near 3) that would drag a mean far above the typical case.

**Decision:** A single national detour factor is a **documented limitation**, not a hidden approximation.
**Reason:** The ratio genuinely varies by geography — a block with a direct path is near 1.2, one that must detour to an overhead bridge across an expressway can exceed 2.5. One constant cannot be right for both. `docs/detour-calibration.md` reports the median with quartiles and range, and names per-area factors as future work rather than pretending the constant is exact.

## 5. Build plan and testing

**Decision:** Week 1 starts with a **walking skeleton** — 3 hardcoded neighbourhoods, 2 factors, made-up scores, real Flask app and real page flow.
**Reason:** Proves the architecture end to end before any ETL work, gives the second person something to integrate against, and means there is always something demoable. Building the ETL perfectly for two weeks with no running app is how student projects end up with nothing to show.

**Decision:** Tests are written **alongside** the code, not in a testing phase at the end.
**Reason:** The golden test (fixed mini-snapshot, hand-calculated expected scores) is what catches a scoring change that silently breaks the Accuracy NFR. Written after the fact, it only confirms whatever the code currently does. The formal test *documentation* deliverable is still produced in week 4.

**Decision:** **Black-box** testing by equivalence partitioning and boundary values; **white-box** testing by branch coverage of the scoring engine.
**Reason:** The FRs already state every boundary (2/4 neighbourhoods, weights 1–10, 1–4 categories, 6-digit postal codes), so black-box cases follow from the spec. The scoring engine's important branches — missing data, all factors excluded, joint rank — would otherwise never run in normal testing.

**Decision:** All external adapters are **mocked** in tests.
**Reason:** Tests must not hit the network: they'd be slow, flaky, and would fail when OneMap rate-limits.

**Decision:** Six screens — home; Where to Live setup; Where to Live results (with breakdown as a modal); Lepak search; Lepak results; event detail with route map. Plus a shared error/empty state.
**Reason:** Small enough to rebuild if the first attempt is ugly, and it maps one-to-one onto the use cases.

## 6. Documentation and process

**Decision:** Use cases are **goal-level** (10 total), not one per screen action.
**Reason:** "Select neighbourhoods" delivers no value on its own — it is a step, and belongs in the use case description. Avoids the functional-decomposition anti-pattern.

**Decision:** Every `«include»` is used by **two or more** use cases.
**Reason:** An include used once is decomposition, not reuse. Plan Route is used by two use cases, Resolve Location by three.

**Decision:** Failure handling lives in **alternate flows and exceptions**, not as use case bubbles.
**Reason:** This is why "Serve Last-Known-Good Snapshot" was removed and folded into UC-9's exceptions.

**Decision:** Scheduled ingestion has **initiating actor: NULL**; no Scheduler actor is drawn.
**Reason:** Follows the convention used in Deliverable 1 — a scheduler is internal to the system, not an external entity.

**Decision:** NFR targets rewritten to be **verifiable**.
**Reason:** "80% of first-time users" needs a study we won't run, and "within 60% tolerance" constrains nothing. Replaced with a 5-person usability test, concrete performance targets, and accuracy exact to 1 decimal place.

**Decision:** Compatibility narrowed to **Chrome and Firefox on desktop, plus mobile browsers**.
**Reason:** We cannot test Safari on Windows or eight browser versions. Claim only what we test.

**Decision:** An **attribution footer** — OneMap (SLA), © OpenStreetMap contributors, data.gov.sg.
**Reason:** OneMap requires visible attribution and OpenStreetMap is licensed under ODbL. One line, and it reads as professional.

**Decision:** Cut order if week 4 slips: **parking (UC-3) → event route view (UC-2) → commute (UC-6)**.
**Reason:** All three are `«extend»`, so removing one doesn't break its base use case — a real benefit of the diagram structure, worth stating in the report. Never cut: Where to Live end to end, and a Lepak list with travel times.

**Decision:** Requirements documents are compiled **in one pass** once decisions settle, not edited after each change.
**Reason:** Avoids version drift across FR, NFR, Data Dictionary, and ten use case descriptions that all cross-reference each other.

## 7. Channel assessment (30 Sep 2026)

| Channel | Verdict | Evidence |
|---|---|---|
| @sgweekend | **Use** | ~4–5 posts/week; 13 of last 15 had a date and a named venue |
| @sgwhereto | **Use** | 14.5k subscribers, ~3–5 posts/week; 8 of last 10 had a specific date, 9 of 10 a named venue. Mix of events and retail promos — the Sales & Pop-ups category covers those |
| @sgnightlife | **Reject** | A 20k-member group, not a broadcast channel. No post feed in the web view, and group messages are people talking, which we excluded on privacy grounds |
| @SGArtsChannel | **Use** *(14 Oct)* | Public broadcast channel, ~3–4 posts/week; all 8 recent posts had an event date and a named venue (galleries and museums). Posts are long-running exhibitions, so they stay valid for weeks — useful for demo resilience. None give a clock time, which is what the all-day rule exists for |
| @SGClubbing | **Reject** *(14 Oct)* | A 20k-member group, not a channel; no feed |
| @LiteracyEventsSG, @SGGreenChat | **Reject** *(14 Oct)* | No feed at `t.me/s/` — either no such channel, or the web preview is disabled, which puts them out of reach without the Telegram API we rejected |

| @sgconcerts | **Use** *(14 Oct)* | 94.9k subscribers; every recent post carries an event date, named venue and start time. The highest-quality source found |
| @dateideas | **Use** *(14 Oct)* | 60.1k subscribers, Singapore-specific; most posts name a venue and many give dates and opening times |
| @sgfitnesshealth | **Use** *(14 Oct)* | 24.3k subscribers, ~5–8 posts/week; a mix of dated events and undated guides |
| @TimeOutSG | **Reject** *(14 Oct, corrected)* | **Dormant** — newest post 19 Jun 2026, and only 8 of its 40 newest posts pass the date pre-filter. An earlier assessment here claimed ~14 posts/week; that was inferred from clustered posting *times* on the web preview, which shows no dates. Frequency cannot be read from that page — only the newest post's date and the post-ID range are reliable |
| @sgbestnightlife | **Use, on probation** *(14 Oct)* | A real channel, but posts are weekly roundups with no per-item dates. Kept because discards are logged, so the yield data can justify dropping it |
| @singaporeruncalendar | **Reject** *(14 Oct)* | Dormant — the two newest posts are admin notices about 17 months of owner inactivity, and some events are overseas (Bali) |

Six confirmed: @sgweekend, @sgwhereto, @SGArtsChannel, @sgconcerts, @dateideas, @sgfitnesshealth — plus @sgbestnightlife on probation (17 of its 40 newest posts pass the date filter; alive but thin). The test for any new one is whether `t.me/s/<name>` shows posts in a browser; channels say "subscribers", groups say "members".

## 8. Open items *(reviewed 14 Oct 2026)*

- *All four of Sarthak's tasks (S2 scraper, S3 templates, S4 diagrams and test table) were delivered and merged by 14 Oct. Templates are responsive with Leaflet and Chart.js vendored locally — no CDN.*
- **Recompile the deliverable** — FR, NFR, Data Dictionary and use case descriptions, against what was actually built. Several FRs are now knowingly out of date; see §17.
- **A wifi-off rehearsal with the network genuinely down** — the one run so far used a dead proxy, and a captive portal behaves differently.
- *Settled since the last review:* the channel list (§7, seven usable), the division of work (`Sarthak.md`), and the Where to Live review findings (§16).

## 9. Data source decisions (30 Sep 2026)

**Decision:** "Hospitals" means the **9 public acute general hospitals** (SGH, CGH, TTSH, NUH, KTPH, NTFGH, SKH, Woodlands, plus Alexandra). Private hospitals, community/step-down hospitals, psychiatric hospitals, specialty centres and the prison medical facility are excluded.
**Reason:** The original instruction — "24-hour emergency department, public and private" — turned out to match **no private hospital**. MOH states that private hospitals "are not configured to provide the full range of emergency and trauma services"; what they run are 24-hour Urgent Care Centres, which are not equivalent. Decisive argument: in an emergency you do not choose your hospital — SCDF conveys emergency cases to public hospital emergency departments, so living beside a private hospital does not change emergency access. Alexandra is included despite having an Urgent Care Centre rather than a full ED, because it is a public general hospital and the category is coherent only if it contains all of them. Routine private care is already covered by the separate GP clinics option, so nothing is lost by this choice.

**Decision:** The alternative rule (17 hospitals, adding Alexandra and 8 private) is **recorded as a rejected option**, with its effect measured.
**Reason:** It is not a marginal choice: it moves the hospital score by up to 7.4 points and changes 31 of 32 area ranks by up to 23 places (Marine Parade 31→8 via Parkway East, Downtown Core 18→2 via Raffles, Rochor 7→1), while heartland areas fall (Punggol 10→16, Hougang 15→21) because private hospitals are all central or east. A ranking that swings that far on a definition must have the definition documented, not buried.

**Decision:** The UI states what the hospital option measures: distance to **public acute hospitals**.
**Reason:** Transparency NFR. A user who would use private care can see what the number does and does not cover.

**Decision:** KK Women's and Children's Hospital is **excluded** from the hospital set.
**Reason:** Its 24-hour emergency service covers children and women only, so it is not a general emergency option. MOH's own ED attendance statistics footnote it as excluded.

**Decision:** Hospital classification lives in `data/reference/hospitals.csv`, covering **all 31** hospitals in MOH's OneMap theme, not only the included ones, with a source URL per row. A hospital appearing in the theme but missing from the file **stops the build**.
**Reason:** Provenance per row makes the category defensible in the QnA, and the build-stopping check means a future data refresh cannot silently drop a hospital into an unclassified state.

**Decision:** Polyclinic locations come from a **hand-compiled reference file** (`data/reference/polyclinics.csv`, 28 polyclinics), because no government dataset gives polyclinic locations.
**Reason:** Checked and rejected: MOH's "Health Facilities (Primary Care, Dental Clinics and Pharmacies)" holds yearly counts with no names or addresses; "Vaccination_Polyclinics" covers 8 of ~26; the Cervical Screening dataset is older and disagrees on two postal codes, apparently relocations. The compiled file uses maps.gov.sg's official polyclinic listing (26 with addresses, updated 7 Dec 2025) plus cluster sites for the two it omits, carries a source URL and retrieval date per row, and its counts reconcile with each cluster's stated total (SingHealth 10, NHG 10, NUP 8). All 26 cross-checkable entries geocode to within 45 m of the government listing's own coordinates. Facilities MOH lists as opening after 2026 are excluded.

**Decision:** GP clinic data is the CHAS dataset, **last updated 26 September 2021** — five years old. *(Corrects an earlier note saying two years: June 2024 was data.gov.sg's listing metadata, not the data's own update date.)*
**Reason:** No fresher government source exists — OneMap has no CHAS theme, and the CHAS clinic locator is a web page, not a dataset. The date is recorded in snapshot metadata, shown in the UI, and stated in the report as the project's most significant data limitation.

**Decision:** The rail caveat date is **17 July 2026**, computed from the data itself. *(Corrects an earlier 2 Dec 2025 figure, which was the first record's date rather than the latest.)*
**Reason:** The UI note must reflect what the data actually contains, and computing it from the data means it stays true after a refresh.

**Decision:** The "far from rail" note triggers above a flat-weighted median of **1,500 m** to the nearest exit, flagging Changi (3,518 m) and Tengah (1,704 m).
**Reason:** The distribution has a clean gap — the next area is Pasir Ris at 1,002 m. Tengah's low score is correct today (its Jurong Region Line stations are not open and are not in LTA's data) but would read as a bug without the note.

**Decision:** Greenery measures distance to the **park polygon edge**, using 462 NParks park and nature-reserve polygons, plus the 336 km built park connector network.
**Reason:** Measuring to a park's centre point would be the same class of error as counting stations instead of measuring walks — a test case in the code shows a block 111 m from a park edge sits 667 m from its centre. Only built connectors are used, not Master Plan layers containing planned routes, for the same reason the Tengah caveat exists.

**Decision:** Greenery limitations stated in the report: only NParks-managed parks count (not Town Council estate greens), the dataset counts ~158 playgrounds as parks, and the Botanic Gardens is absent from it.
**Reason:** National figure is 73.4% of flats within 400 m, ranging from 100% (Outram) to 45.5% (Serangoon). Those limitations are the honest caveats on that number.

## 10. Amenities, Commute and data-source corrections (30 Sep 2026)

**Decision:** Amenities aggregates the capped counts with a **flat-weighted mean**, not a median. *(Changed 30 Sep after measuring the median's behaviour.)*
**Reason:** The median was chosen to stop one block with twenty cafés distorting an area — but the **per-type cap of 3 already removes outliers**, so the median's only advantage was gone while its cost remained. Measured: with a median, selecting supermarkets alone leaves **28 of 32 areas tied** at the cap, and libraries alone leaves 25 of 32 tied at 0 — a user selecting one amenity type would learn almost nothing. The flat-weighted mean cuts the largest single-type tie from 28 areas to 5, leaves multi-type selections with no ties at all, and is still hand-checkable as a weighted average, which the Accuracy NFR requires.

**Decision:** Commute modes are **public transport and drive** only.
**Reason:** OneMap also offers walk and cycle, but neither describes a daily commute across planning areas. Named as future work rather than built.

**Decision:** Public-transport commute routes depart at **08:30 on the next weekday**.
**Reason:** OneMap requires a departure date and time, and results vary by both. The morning peak is what "my commute" means, and fixing it makes the score reproducible — an unfixed departure time would silently change the answer depending on when the user ran the comparison. Stated in the factor note the user sees.

**Decision:** Library locations come from **NLB's OneMap theme**, not data.gov.sg's Libraries GeoJSON.
**Reason:** The data.gov.sg records last changed in April 2019 and predate Punggol Regional Library. Recency beats the more obvious source.

**Decision:** SFA's supermarket licence list is used as published, including minimarts and a butchery, with **25 of 476 unplaceable postal codes logged** (one is literally "0000na").
**Reason:** That is what SFA licenses as a supermarket; reclassifying by hand would be our judgement substituted for the regulator's. The unplaceable records are counted in snapshot metadata rather than silently dropped.

**Decision:** OpenStreetMap results are **clipped to Singapore's planning areas**.
**Reason:** The Overpass bounding box pulled in 21 malls, 6 gyms and 79 cafés in Johor Bahru.

**Decision:** OneMap request data is **redacted from all logs and error text**, and `urllib3` request logging is pinned at INFO.
**Reason:** Discovered during implementation: OneMap echoes the request coordinates back in its route responses, and `requests`' connection-error text contains the full URL and query string — so an ordinary stack trace or a DEBUG log would have written the user's destination postal code to disk, breaking the Security NFR. Tests assert the postal code never appears in logs, exception text, or on disk.

**Decision:** Bukit Timah's commute origin is **Toh Yi Drive, holding 72% of its flats** — a stated limitation, kept after testing the alternative. *(Corrected 30 Sep: the earlier "1,026 m from the centroid" framing measured the wrong thing, since that centroid sits on empty ground between two clusters.)*
**Reason:** Bukit Timah's flats form two clusters about 4 km apart — Toh Yi Drive (72%) and Queen's/Empress Road (28%) — so **no single origin can serve both**. A medoid origin was measured as an alternative: it does not fix Bukit Timah either (it also lands in Toh Yi Drive) and it moves 23 of 32 origins for at most a 4% gain in representativeness. Keeping the simpler rule with an honest limitation beats churning every area's origin for nothing. The note reads: commute is timed from Toh Yi Drive and does not describe the Queen's Road/Empress Road blocks.

## 11. Where to Lepak — event categories (30 Sep 2026)

**Decision:** Eight event categories, fixed: **Food & Markets · Arts & Culture · Music & Performances · Sports & Fitness · Family & Kids · Workshops & Classes · Community · Sales & Pop-ups**. The user selects 1–4; the LLM must assign each extracted event to exactly one.
**Reason:** A closed list is what makes validation possible — an event whose category is not on the list is discarded, which is the main defence against an LLM inventing a plausible-sounding field. It is also what lets the results page offer category chips without a schema change. Eight is enough to be useful for filtering without giving the user more checkboxes than they will read, and the set was drawn from what the confirmed channels actually post: *Sales & Pop-ups* exists because a large share of @sgwhereto's posts are retail promotions rather than events, and *Community* covers CC and RC activities, which are the ones most tied to a specific neighbourhood.

**Decision:** Categories are defined in one constant (`gowhere/lepak/categories.py`), not spread across the extraction prompt, the validator and the UI.
**Reason:** The same list is used in three places — the LLM's allowed values, the discard rule, and the search form. Three copies would drift, and a drift between the prompt and the validator would silently discard valid events.


## 12. Venue matching (30 Sep 2026)

**Decision:** Venue matching stays **strict** — the whole query must appear word for word in a OneMap name or address — and unmatched venues are **discarded and logged**.
**Reason:** A wrong venue is worse than a missing one: it sends the user to the wrong place with a confident travel time attached. Strict matching rejected "Tampines 1", which would otherwise have resolved to Tampines Avenue 1, and "Capitol Singapore", which OneMap knows only as "Eden Residences Capitol". The cost is real — 2 of 13 currently-running events in the fixture run — and is stated as a limitation.

**Decision:** Coverage is recovered through a **hand-curated alias file** (`data/reference/venue_aliases.csv`: alias, postal code, source, date), populated from the discard log, rather than by loosening the match rule.
**Reason:** The channels repeat the same venues — malls and landmarks — so a small alias table buys most of the missing coverage. It keeps every match auditable, the same pattern already used for polyclinics and hospitals, instead of trading accuracy for coverage everywhere at once.

## 13. Where to Lepak — search behaviour (30 Sep 2026)

**Decision:** Events whose route fails are **listed last with an estimated straight-line distance**, not hidden.
**Reason:** They passed the distance pre-filter, so they are plausibly reachable; hiding them would hide the failure from the user and from us. Matches FR 2.2.6, which requires the straight-line distance labelled as estimated rather than a bare "unavailable".

**Decision:** A short trip with **no public-transport itinerary falls back to a walking route**, labelled as walking.
**Reason:** OneMap returns no itinerary for a trip that is too short to involve transit — a live case was an event at the user's own starting point. Showing "unroutable" there would be absurd. The label matters: an unlabelled fallback would show a walking duration under a public-transport heading.

**Decision:** Date options are **today, tomorrow, this weekend, next 7 days, next 30 days** — presets only, with no custom date range. Maximum travel time offers **15/30/45/60/90 minutes** and accepts 5–180.
**Reason:** Presets cover what people actually search for, keep the form to one control, and make the black-box test cases finite. A custom range was in the original FR; it is dropped because it adds a date-validation surface (end before start, start in the past) for a case the presets already cover. **The FR document must be updated to match when the deliverables are recompiled.**

**Decision:** Straight-line pre-filter uses deliberately **loose top speeds** — walk 100, public transport 1,000, drive 1,500 m/min.
**Reason:** Measured real routes ran at 66, 180 and 335 m/min, so the filter cannot discard an event a real route would have kept. A pre-filter that is too tight silently loses results; one that is too loose only costs a few routing calls.

**Decision:** Routing runs **16 workers in parallel**, with backoff on HTTP 429.
**Reason:** Measured: 40 public-transport routes took 7.4 s at 8 workers and 3.1 s at 16, so the 50-event cap fits inside the 8-second Performance target. A live search already hit one 429 and recovered, so the backoff is load-bearing, not theoretical.


## 14. Offline resilience and demo (30 Sep 2026)

**Decision:** Request-time external calls use **1 retry and an 8-second timeout**, separate from the ETL's 4 retries with backoff. Failed postal lookups are remembered for 60 seconds.
**Reason:** Found in the first offline rehearsal: request-time OneMap calls had inherited the ETL's retry policy, so with the network down a comparison took **63 seconds** and a reload 32. The ETL can afford to retry patiently overnight; a user waiting on a page cannot. After the fix the same offline comparison takes 2.5 s. Retry policy is a property of the caller, not of the adapter.

**Decision:** Retry backoff is **jittered** to 50–150% of each step.
**Reason:** Without jitter, 16 parallel workers retry in lockstep and re-create the burst that caused the 429.

**Decision:** `data/snapshot.db` is **committed to the repository** despite being generated data (~11 MB).
**Reason:** A clean clone must be able to run the app. Rebuilding it needs about an hour of geocoding with a working network, which is not something to discover the day before a demo. 11 MB is well inside GitHub's limits, and the file is reproducible from the documented ETL command, so committing it costs nothing but disk.

**Decision:** Front-end libraries (Leaflet, Chart.js) are **served from `gowhere/web/static/`, not a CDN**.
**Reason:** The Reliability NFR invites exactly the test of unplugging the network, and CDN-loaded libraries would take every map and chart with them. Basemap tiles cannot be bundled, so offline the planning-area outlines render on a blank background — the shapes still appear.

**Decision:** Add an **offline fallback for postal-code lookup**, using the ~11,000 HDB postal codes already geocoded in the snapshot.
**Reason:** It is the last thing that fails completely offline — a Lepak search by postal code cannot resolve at all, leaving only "Use my location", which may itself be denied on a demo machine. The data is already in hand, so the fallback is nearly free. It covers HDB addresses only; a non-HDB postal code still needs the network, and says so.

## 15. Known gap (1 Oct 2026)

**Open:** The Public Transport factor is **rail-only**. `PublicTransportScorer` has no `options()`, so the MRT/LRT · Bus · Either choice promised by FR 1.2.4 and the Data Dictionary does not exist yet.
**Reason:** Bus stop and service data comes from LTA DataMall, which needs an account key nobody has registered for. Everything else in the factor — the qualifying-bus-stop rule (3+ services), the per-block distances, the 0.7/0.3 blend — is specified and ready. **Either register for the key and build the option, or amend FR 1.2.4 to describe a rail-only factor before the deliverable is recompiled.** What must not happen is the document promising a control the product doesn't have.

## 16. Where to Live — review findings settled (14 Oct 2026)

**Decision:** The results page shows a **grouped horizontal bar chart** by default — one group per factor, one bar per neighbourhood. The radar chart may remain as a secondary toggle but never as the only chart.
**Reason:** FR 1.5.3 specifies a chart on the results page, and the implementation had only a radar chart inside a pop-up. Radar also misleads: the enclosed *area* looks meaningful when it is an artefact of the axis order.

**Decision:** The score breakdown (FR 1.4.4) displays, for each included factor, the **importance weight, both the recommended and runner-up neighbourhoods' category scores and raw values, and the marginal contribution** sorted by size — plus the overall formula with the user's weights filled in, and every excluded factor with its reason (user-excluded, or data unavailable).
**Reason:** This is the Transparency NFR's only evidence. Every value is already computed; it simply was not displayed.

**Decision:** Factor defaults: **five factors included by default** (Public Transport, Housing Affordability, Amenities, Greenery, Healthcare); **Commute is off and greyed**, and switching it on reveals its destination postal code field. All six amenity types are ticked; healthcare defaults to GP clinics. **FR 1.2.2.1 is amended from "all" to "all except Commute", and FR 1.2.8.1's postal code requirement becomes a condition for Commute being scored rather than for submitting the comparison.**
**Reason:** Commute cannot be computed without an input only the user can supply, so "included by default" would mean a first-time user is blocked from submitting until they either type a postal code or switch a factor off. Two alternatives were considered: starting *every* factor off (explicit, but a grader must tick six toggles before the app does anything) and auto-excluding Commute silently at submit (never blocks, but hides the dependency). The chosen behaviour makes the dependency visible at the moment the user reaches for the factor, while a comparison still works on the first click.

**Decision:** Build the **Bus and Either options** for Public Transport (FR 1.2.4) rather than amending the FR to a rail-only factor.
**Reason:** It is the only gap that deletes a promised control, and it is the most visible personalisation in the feature — someone who travels by bus gets a different answer. The machinery already exists: nearest-qualifying-facility distance per block is what Greenery and Healthcare do. Needs bus stops plus routes from LTA DataMall (to count services per stop for the 3-or-more qualifying rule), an `options()` method on the scorer, a snapshot rebuild and an updated golden test. The DataMall key is registered.

**Decision:** The stale-snapshot warning (FR 3.1.6) ships with a test that **forces an old date**.
**Reason:** The live snapshot was built on 30 Sep 2026, so the warning cannot fire naturally for a year — it would otherwise ship untested and silently broken.


## 17. Where to Lepak and deployment — review findings settled (14 Oct 2026)

**Decision:** Build the four unimplemented Lepak requirements as specified: the **freshness line** with a 24-hour warning (FR 2.3.4), **restoring sort, chips and page** when returning from an event (FR 2.5.3), **independent category chips** that hide one category while keeping the rest (FR 2.4.2), and a route map with a **starting-point marker and step-by-step directions** (FR 2.5.2).
**Reason:** All four were specified and simply not built. Three are visible within seconds of a grader using the app — clicking an event and losing your place is the most obvious of them — and the freshness line is what shows a demo audience the data is live rather than fixtures.

**Decision:** Three FRs are **amended to match the code**, not the other way round.
**Reason:** Each was a deliberate decision taken during implementation, and reverting the code would make the product worse. **FR 3.2.1** becomes 6-hourly ingestion, not hourly, because cost tracks post volume rather than frequency (§3). **FR 2.1.3** drops the custom date range in favour of presets, removing a date-validation surface for a case the presets already cover (§13). **FR 2.1.6** gains the 90-minute travel-time option, because Singapore-wide trips exceed 60 minutes.

**Decision:** The application runs as **one process** — Waitress serving the app with the ingestion scheduler on a background thread, behind a single documented command.
**Reason:** Session state lives in memory, so it must be single-process regardless; and one command is one thing to go wrong during a demo. Flask's development server is not something to present. Waitress is pure Python and runs on Windows, unlike gunicorn.

**Decision:** The 6-hourly schedule is **off by default**, enabled by an explicit flag documented as the demo-day setting. Ingestion is run manually until then.
**Reason:** The team is demonstrating to groupmates well before demo day; a background job polling eight channels every six hours earns nothing until the data needs to be current, and an always-on scheduler is one more thing to misbehave while the app is still changing.

**Decision:** Stored event text has `<` and `>` stripped, **in addition to** escaping on output.
**Reason:** A code review found a real stored-XSS path: a venue name containing HTML executed when the user hovered a map marker, confirmed in a headless browser. The text comes from public Telegram posts — exactly the untrusted-input case the prompt-injection rules exist for — and the marker tooltip was writing it as HTML. Escaping on output is the correct fix; stripping on input is defence in depth for the next template that forgets. **This belongs in the report's security section:** it is the third defect found by taking untrusted input seriously, after the `round()` rounding bug and the postal code leaking through OneMap's error text.


## 18. Bus access saturates (14 Oct 2026)

**Finding:** Built exactly to the Data Dictionary, the Bus measure carries almost no information. **30 of 32 areas have 100% of flats within a 10-minute walk** of a qualifying stop (lowest 97.4%), and flat-weighted median walks span just 0.5–2.7 minutes. Even a 5-minute threshold leaves every area above 87%. So 70% of the Bus score would be a percentile rank of differences of a few tenths of a percent — noise dressed as a score.

**Decision:** Redefine the Bus measure as **service richness**, not walking distance: `0.7 × percentile(flat-weighted median number of distinct bus services reachable within 400 m) + 0.3 × percentile(flat-weighted median walk to the nearest qualifying stop)`.
**Reason:** The two modes differ in kind. Rail is **scarce**, so how far you walk to it is the whole question. Buses are **ubiquitous** — Singapore's network puts a stop within three minutes of essentially every HDB flat — so distance cannot discriminate, and what actually varies is *how many places you can get to* from the stops near you. Keeping the same two-component shape and the same 0.7/0.3 split as rail means only the access measure changes, not the formula. The data is already in hand: 26,833 route rows give the services at each stop, so no new source is needed.

**Decision:** With the two modes measured differently, **Either = the higher of the two mode scores**, replacing "whichever is nearer".
**Reason:** "Nearer" is meaningless once the measures aren't comparable. "Whichever mode serves you best" is what a user choosing Either actually means, and it stays hand-checkable. Note in the report that the maximum of two percentile ranks is not itself a percentile rank, so Either scores sit higher than either mode alone.

**Decision:** The saturation finding is reported as a **result, not a defect**.
**Reason:** "We implemented the specified measure, measured it on real data, found it could not discriminate, and changed the measure for that mode" is a stronger story than a measure that happened to work. It is also a genuine fact about Singapore worth stating: bus access is near-universal, so it is not a useful basis for choosing between neighbourhoods — rail access and service variety are.


## 19. LLM provider, first live ingestion, and a retracted finding (14 Oct 2026)

**Retraction:** The claim that "routing was dead for eleven days because the OneMap token expired" is **unproven and must not appear in the report.** Tested directly: OneMap accepted the 30 Sep token with HTTP 200 eleven days past its JWT `exp` claim, while a malformed or missing token gets a clean 401. So OneMap is not currently enforcing expiry, and whatever caused the earlier failures, that explanation does not hold.
**Reason this is recorded rather than deleted:** the story was plausible, tidy, and wrong — a token with a visible expiry date, failures starting three days later. It was nearly written into the report as established fact. Self-renewal is still the right design, because nothing guarantees an old token keeps working, and it is verified live: a token due to expire in 60 seconds was replaced by a fresh 72-hour login. The code's warning was softened from "routing will fail" to "may be refused". **Keep this as a report item about verifying causes rather than inferring them.**

**Decision:** The LLM provider is **OpenAI**, model `gpt-6-luna`, with reasoning effort set to low.
**Reason:** The user supplied an OpenAI key. The model is documented for high-volume work at $0.10/M input and $0.50/M output; it is a reasoning model and reasoning tokens bill as output, hence low effort. The schema is sent as a strict JSON schema through Structured Outputs — our own validator is kept anyway, because it is also the defence against an injected post inventing a field.

**Evidence for the Supportability NFR:** the provider swap changed **the adapter class and nothing else in production code**. One test outside it changed, because it had been built around an Anthropic-shaped fake client — test coupling, not a production leak, and worth reporting honestly as such. This is a stronger demonstration than the planned case, because nobody arranged it in advance.

**Measured, first live ingestion (14 Oct, 7 channels):** 135 posts fetched → 25 dropped by the pre-filter → 110 sent to the model → 140 events extracted → **28 stored**, later **38** after the alias recovery run (§20). Discards: 53 already ended, 38 with no single venue, 21 venue not placed, 0 schema failures, 0 duplicates. Cost: 13 calls, 28,095 input and 14,424 output tokens, **US$0.0100 for the run**.
**Reason this is recorded in full:** it is the project's only real measurement of extraction quality, and the discard breakdown is more useful than the headline. Three honest caveats: "already ended" is inflated because a first run reads weeks-old posts; "no single venue" is mostly roundup posts listing several events; and "venue not placed" is partly our own strict matcher rather than the model.

**Decision:** Drop **@sgbestnightlife**.
**Reason:** 0 events stored from 20 posts, with only 6 passing the date pre-filter. It was kept on probation precisely so the yield data could decide, and it has.

## 20. What the first run actually discarded (14 Oct 2026)

**Finding:** Of the 21 events discarded as "venue not placed", **10 were our failure, not the model's** *(corrected from 12: one Esplanade event had been extracted twice, and one post was miscounted — 11 discard rows covering 10 distinct events)*. The model produced good venue strings — KC Arts Centre, Suntec Convention Centre, Esplanade Recital Studio, Great World, F1 Pit Building. Two causes: OneMap knows several of them under a different name (Isetan Scotts is Shaw House; Clarke Quay Central is The Central; the F1 Pit Building is The Pit Building), and our strict matcher rejected genuine OneMap hits because the name was not a contiguous substring ("Suntec Convention Centre" against OneMap's "Suntec Singapore Convention & Exhibition Centre").
**Decision:** Recover them through **10 alias entries**, each with a source and a verification date, rather than by loosening the matcher. All 10 are now stored. The remaining 10 — eight SGArtsChannel galleries plus Gravity by Noir and RASA Space, whose posts give no address at all — stand as genuine misses.
**Reason:** Same reasoning as §12: a wrong venue sends someone to the wrong place with a confident travel time attached. Aliases keep every match auditable; a looser matcher would silently affect every venue in the system to fix ten.

**Decision:** The proposed matcher rule — treating several exact-name hits with no postal code as one place when they are all parks — is **recorded as future work, not built**.
**Reason:** It would recover roughly one event (Fort Canning Park, which OneMap returns as two distant entries) at the cost of a special case in the matching rules — and that event is now stored via an alias in any case. The alias file already handles such venues with provenance.

**Finding:** The 38 events discarded for having **no single venue are genuine**, and the prompt was not changed.
**Reason:** Investigated rather than assumed. The model splits roundup posts correctly into one event per item and fills in the venue wherever the text names a place. The discarded items name no place anywhere — "Free Workouts & Runs This Weekend" with names and dates only, F1 pop-up lists of brands, "all outlets" chain deals. **A prompt change could only have made the model guess venues**, which would produce exactly the wrong-venue failure the strict matcher exists to prevent. Reported as a measured limit of the source material rather than tuned away.

**Decision:** The discard log records the model's **venue and address strings**, not just the event title.
**Reason:** Diagnosing this bucket required re-fetching and re-extracting the posts, because the log did not record what the model had actually produced. That cost a run; without the fix it would have cost one every time.

## 21. Browser rehearsal findings (15 Oct 2026)

**Finding:** A **concurrency bug** that no HTTP-level test had reached: the snapshot shared one SQLite connection across Waitress threads, so two overlapping `/live/check` requests — which the setup form issues as the user clicks — returned HTTP 500. Each thread now gets its own read-only connection, and the regression test fails 3 times out of 3 against the old code.
**Reason this matters for the report:** it only appeared once the app was driven through a real browser by a user clicking quickly, because every earlier test issued requests one at a time. It is the clearest argument in the project for rehearsing the way a user actually behaves rather than the way a test harness does.

**Decision:** Pin `shapely<2.2`.
**Reason:** A fresh clone installs Shapely 2.2, which deprecates `shapely.ops.transform` and prints 110 deprecation warnings on every ETL run. A pin is one line and keeps a clean checkout quiet; migrating the call is future work, not demo-week work.

**Decision:** Draw the **starting point on the event map whenever it is known**, not only when a route exists.
**Reason:** Offline, or for any unroutable event, the map currently shows a single venue pin on a blank background at street zoom, which tells the user nothing. With both points shown, the "About 5.5 km away (straight-line estimate)" text has something to correspond to — the degraded state becomes informative rather than merely not broken.

**Decision:** The phone-width comparison table stacks each factor's **summary beneath its scores**, rather than beside them.
**Reason:** The table scrolls correctly inside its own box, but at 390 px the factor columns are so narrow that summaries wrap to one or two words per line and every row becomes very tall. A CSS-only change at a phone breakpoint.

**Decision:** The **8-second Performance target stands** for Lepak search. *(Settled 15 Oct on measurement.)*
**Reason:** Measured over a clean set of 10 runs — fresh browser session each time, timed from click to page load, with the instrumentation wait removed: **median 5.14 s, 90th percentile 6.11 s, maximum 6.15 s**, every run routing 20 events. Across all 19 successful browser runs the maximum was 6.93 s. The earlier 8.06 s figure included a 0.5 s instrumentation wait and came from a sample of four. The 50-event cap was never the constraint, so lowering it would have changed nothing.

**Recorded honestly alongside it:** one browser attempt out of 20 returned no page within 60 seconds, while the server stayed responsive and the six HTTP runs immediately afterwards took 4.1–7.2 s — cause undetermined, most likely the headless browser, which dropped a connection in another batch. And OneMap answered some routing calls with HTTP 429 when searches were repeated every 10–15 seconds; the retry recovered every time. Neither is hidden in the write-up.

**Finding worth keeping:** Puppeteer's **full-page screenshots silently drop Leaflet's SVG layer and map tiles**, which is why earlier online screenshots showed grey backgrounds even though 14–15 tiles had loaded. Element screenshots are reliable. A screenshot is evidence about the screenshot tool as much as about the page — worth remembering before reporting a visual defect that is an artefact of how it was captured.

## 22. Interface redesign (15 Oct 2026)

The two screens the team found dullest were the Where to Live setup — 32 checkboxes in
a block — and the Where to Lepak results, which were unbroken grey text. Both are now
rebuilt. The visual system is editorial minimalism: a warm monochrome canvas, one serif
(Instrument Serif, SIL OFL, vendored) for display type, colour reserved for category
tags and semantic state.

### Event pictures: Wikipedia venue photographs, not Street View

**Decision:** Each event card carries a **freely-licensed photograph of its venue**,
taken from the English Wikipedia article that sits at the event's own coordinates, with
generated **category artwork** as the fallback. Resolution is an offline step
(`python -m gowhere.lepak.images`) that downloads into `gowhere/web/static/venues/` and
writes a manifest; rendering only reads the manifest.

**Reason Street View was rejected**, although it was the original proposal:

| | Street View Static API | Wikipedia geosearch |
|---|---|---|
| Key | Required, **with billing enabled** | None |
| Key exposure | In the image URL, visible in page source | — |
| Caching the image | **Forbidden** (Maps Platform terms §3.2.3(b); only `pano_id` may be stored) | Permitted; CC licences |
| Offline | **Breaks** — every card calls Google on every page view | Works; files are in the repo |
| Cost | Pro-tier SKU, paid beyond a small monthly free allowance | Free |
| What you see | Whatever road is nearest the centroid | The building itself |

The last row decided it as much as the licence. Our events cluster in the CBD, so
centroid Street View would have returned the same few expressways and carpark ramps
over and over. The Esplanade card now shows the Esplanade.

**Decision:** A match is accepted at **0.62** on a score that is half character
similarity and half token overlap (`gowhere/lepak/images.py::match_score`).
**Reason:** Character similarity alone scores "Singapore National Stadium" at 0.73
against *Singapore National Eye Centre*, which is next door — a confidently wrong
photograph is worse than no photograph. Token overlap alone punishes "Fort Canning
Park" against *Fort Canning Hill*, which is right. Together they separate the two. On
the 33 venues in the store the automatic pass took 13; `data/reference/venue_images.csv`
names a Wikipedia article for 15 more the geosearch missed or scored just under, giving
**28 of 33**. The remaining 5 show category artwork.

**Decision:** Images are named after the **article**, cropped to **800x450** and
recompressed locally before being committed.
**Reason:** Three separate kinds of waste, found when the 5.2 MB directory was
questioned. Naming files after the *venue* stored four byte-identical copies of the one
Esplanade photograph, and two more pairs besides. Commons does not resize on demand --
it serves the nearest pre-rendered bucket while *reporting* the size asked for, so
requesting 640 px still returned the 960 px file; the trimming has to be done locally.
And those files are often tall portraits, of which the card only ever shows a 16:9
slice. Cropping to the shape actually displayed, at the size actually displayed, took
the worst file from 513 KB to 153 KB. Together: **5.2 MB over 28 files to 2.5 MB over
23**, with no visible change. The crop uses `sips`, which ships with macOS, so nothing
is added to `requirements.txt`; where it is absent the step is skipped and the
full-size download kept. The committed images are already trimmed, so no one else needs
to run it.

**Decision:** The override file names a **Wikipedia article title**, not an image URL.
**Reason:** All four Esplanade halls are rooms in one building; correcting them is one
article name each. Attribution stays automatic, which an image URL would not.

### The neighbourhood picker: MapLibre, not Mapbox

**Decision:** The 32 checkboxes are replaced by a **3D map picker** built on **MapLibre
GL JS** (3-Clause BSD), vendored beside Leaflet and Chart.js. Scrolling the page tilts
the camera from flat to 55°; clicking a town selects it; extrusion height is the town's
number of flats.

**Reason MapLibre rather than Mapbox**, which was what was asked for: Mapbox GL JS needs
a public access token and fetches its style and tiles from Mapbox, so it cannot be
vendored — a clean clone would need a network and an account, and the offline rehearsal
(section 14) would fail. MapLibre renders our *own* polygons from `snapshot.db`, so with
the network off the basemap tiles simply do not arrive and the towns draw on blank,
exactly as Leaflet already degrades. Verified: with every external host blocked the
picker still renders, hovers and selects.

**Decision:** The checkboxes **stay in the DOM**, hidden behind an "Or choose from a
list" disclosure, and remain the form's state; the map only drives them.
**Reason:** The POST contract, the selection-time `/live/check` call and the existing
tests are untouched, and the screen still works with JavaScript off or WebGL missing.

**Decision:** Polygons are served from **`GET /live/areas.geojson`**, simplified to ~66 m.
**Reason:** 42 KB, identical for every visitor, cached for a day — rather than inlining
it into every render of the setup page.

### Chart colour

**Decision:** The chart palette is `#1F6C9F, #B5651D, #6940A5, #00897B`, and a
neighbourhood's colour **follows the neighbourhood, not its rank**.
**Reason:** The old palette was assigned by position in the ranked list, so changing a
weight repainted every town for no reason the reader could see. Colour is now assigned
alphabetically within the selection, and the map polygons reuse it, so one town is one
hue across chart, map and table. The four hues were checked with a validator rather than
by eye: all inside the lightness band, above the chroma floor, worst adjacent pair ΔE
16.5 under deuteranopia and 24.0 with normal vision, all above 3:1 against the page.
Changing any value means re-running that check.

## 23. Waiting state and the category wheel (15 Oct 2026)

**Decision:** A full-screen **waiting orb** on the two submits that genuinely take
seconds, and nothing anywhere else.
**Reason:** Lepak search routes up to 50 events through OneMap — measured median 5.1 s,
90th percentile 6.1 s (section 21) — and until now the page simply sat there with no
sign it was working. Where to Live does the same per area when Commute is on.
Everything else answers from the local snapshot in milliseconds and must not show a
spinner at all.

**Decision:** The overlay appears only after **320 ms**.
**Reason:** A Where to Live comparison with Commute off finishes faster than that.
Showing instantly would flash a spinner that is gone before it can be read, which looks
like a fault. Below the threshold nothing appears; above it, something always does.

**Decision:** The stages are **elapsed-time cues, and deliberately not a progress bar**.
**Reason:** The browser is doing a plain form POST; the server reports nothing until it
redirects, so there is no real percentage to show. The labels name the phases the
request actually passes through, in order ("Finding your starting point", "Working out
how long each one takes"). A bar would claim a precision we do not have. Past 12 s the
overlay says plainly that the wait is abnormal rather than inventing another
reassuring stage, and at 60 s it gives the page back rather than trapping the user.

**Verified across a real navigation** (the page recorded its own timeline into
sessionStorage, which survives the redirect): overlay at 364 ms, stages at 1.3 s, 2.6 s
and 5.6 s, "Ready" at 7.3 s as the response landed, and gone on the results page. Back
navigation restoring from the bfcache clears it, so no one lands on a page stuck behind
a spinner.

**Decision:** The core beats like a **heart** — a quick lub, a softer dub before the
first has relaxed, then a long rest — rather than on an even sine pulse, and two rings
of wake expand out of it on each beat. Measured over one period: the core runs 15 px at
rest, peaks at 21 px, falls to 16, rises again to 19, then holds at 15 for the rest of
the cycle.
**Reason:** An even pulse reads as a machine idling. The asymmetry is the whole effect,
and the long rest is what makes the next beat land. The rings carry only a 5 % swell on
the same rhythm; more and they collide with the dots. The beat is one `--beat` custom
property, so core, glow, wake, ring swell and the brightness wave through the dots all
stay locked together.

**Decision:** The rings spin on a **wrapper element**, separate from the one that beats.
**Reason:** One element cannot run two transform animations at once; the spin would
simply replace the swell.

**Decision:** Under `prefers-reduced-motion` there is **no heartbeat at all** — one slow
breath, no spin, no wake.
**Reason:** A pulsing heartbeat is precisely the kind of motion that setting exists to
turn off. The stage text still updates, so nothing is carried by animation alone.

**Decision:** The orb's rings rotate **in-plane only**.
**Reason:** Tilting them on X to fake a sphere foreshortens the dots along with the
rings, and they stop being dots and become dashes. Depth comes instead from dot size
falling off with radius and a brightness wave running round each ring.

### The category wheel

**Decision:** Where to Lepak opens with a **ring of eight category discs** rather than
eight checkboxes, and **When, Travel by, At most and the starting point appear only
once a category is chosen**.
**Reason:** The old screen asked for five unrelated decisions at once, led by a row of
identical checkboxes. The wheel makes the first decision the only visible one, and each
disc carries the category's own line icon and washed pastel — the same pair already
used by its result-card tag and its fallback artwork, so the colour means the same
thing on every screen.

**Decision:** As with the neighbourhood map, the **checkboxes stay in the DOM** and
remain the form's state; the wheel only drives them.
**Reason:** The POST contract, the validation messages and the tests are untouched, and
with JavaScript off the wheel never appears, the checkbox list is the control, and the
rest of the form is visible from the start. Verified with scripting disabled.

**Found while building it:** a stacked `.form-row` set `flex: 1 1 10rem` on fields whose
main axis had become vertical, so flex-basis was setting each field's **height** — about
10 rem of dead space under every select on a phone. It predates this work and affects
both setup screens; fixed at the same breakpoint.


## 24. Where to Live setup controls (15 Oct 2026)

**Decision:** Each factor's **name is set as a heading** — serif, 1.5 rem, full strength
ink — instead of the small uppercase label every other legend uses.
**Reason:** Six near-identical cards ran down the page under 11 px grey uppercase
legends, so "Commute" and "Greenery" were the least visible words on the screen despite
being the thing each card is about. Every other legend on the site keeps the small
uppercase treatment; only `.factor legend` is promoted, so the contrast between a
section label and a factor name does the work.

**Decision:** Weight is a **slider**, styled like the iOS volume control, not a number
box.
**Reason:** The value is a relative importance from 1 to 10 — something you feel out
against the other five factors, not a figure you type. A slider also makes the whole set
comparable at a glance, which a column of identical number boxes never did. The current
number still shows beside it, and the server validation is untouched, so a posted 0 or
11 is rejected exactly as before and the existing boundary tests still pass.

**Decision:** The filled part of the track is painted as a **gradient driven by a
`--fill` custom property** set in JavaScript.
**Reason:** WebKit has no selector for the part of a range track the thumb has already
passed. Firefox does (`::-moz-range-progress`) and is styled natively. Setting the
variable costs nothing on either, and with JavaScript off the slider still works — the
track is simply uniform, which is how an unstyled range input looks anyway.

**Decision:** The slider is held to **20 rem and may shrink but not grow**.
**Reason:** Stretched across the full card it read as a progress bar reporting
something, rather than as a control you set.

## 25. Where to Eat — scope and signals (19 Oct 2026)

**Decision:** Build **Where to Eat** as a third feature, scoped as *permanent establishments*, and distinguished from Where to Lepak's Food & Markets category by one line: **Lepak is time-bound, Eat is permanent.** A pasar malam this weekend is an event and expires; a hawker centre is open every Saturday and does not.
**Reason:** The two would otherwise overlap confusingly in the UI and in the report. Stating the rule in the Data Dictionary settles it without changing either feature.

**Decision:** Results are **both individual eateries and food destinations** — a hawker centre appears as a single entry carrying its stall count ("Chinatown Complex, 80 stalls, 12 min away").
**Reason:** It covers both ways people decide: "I want laksa" and "let's go somewhere with options". It also plays to data we hold rather than data we would have to buy, and *variety* becomes a free stand-in for the popularity signal no free source provides.

**Decision:** **No star ratings.** Google Places is rejected.
**Reason:** It requires billing, its terms forbid caching the content, and it would break the offline operation the Reliability NFR depends on. Yelp and Tripadvisor have poor or restricted Singapore coverage. A feature that quietly costs money per page view is worse than one that is honest about what it can measure.

**Decision:** Quality is represented by a **badge from a curated Michelin Guide reference file** (name, address, award, source URL, retrieval date), not by a score.
**Reason:** It is a finite, citable list that includes hawker stalls through Bib Gourmand, so it is not merely a list of expensive restaurants. The same provenance-per-row pattern already used for polyclinics, hospitals and venue aliases. A badge claims nothing about relative quality, which is all the evidence supports. Availability and terms to be confirmed before building.

**Decision:** NEA hygiene grades are a **filter, not a sort** — C and D hidden by default, with the user able to show them.
**Reason:** Nearly all licensed establishments are graded A or B, so grading cannot discriminate between results. **This is the bus saturation problem again** (§18): a measure on which almost everything scores the same ranks nothing. As with bus, the distribution is to be measured before the design is fixed, and a sort added only if real spread is found. Hygiene still matters as a floor: few people choose by grade, many would avoid a C.

**Decision:** Cuisine categories are **eight user-facing groups** mapped from OSM `cuisine` tags: Chinese, Malay & Indonesian, Indian, Japanese & Korean, Western, Thai & Vietnamese, Cafés & Desserts, Seafood. Halal and vegetarian come from OSM `diet:*` tags as filters.
**Reason:** Eight matches the event categories, so one UI pattern serves both features, and a closed list makes validation possible for the same reason it does for events.

**Decision:** Where tag coverage is incomplete, places with no cuisine or no opening hours are **shown and labelled**, not hidden, and the measured coverage is stated.
**Reason:** Hiding untagged places would silently delete much of the dataset while appearing to work. The same reasoning as listing unroutable events with an estimated distance rather than dropping them (§13).

**Decision:** Sort options are **Nearest · Open now · Most variety**, mirroring Lepak's three.
**Reason:** A second scoring formula would add documentation and testing work without helping someone choose lunch. Consistency across the two features also means one set of UI behaviour to test.

**To measure before building** — the same evidence-first sequence used for the bus factor and the detour calibration: the NEA grade distribution, OSM `cuisine` coverage, and OSM `opening_hours` coverage across Singapore food venues. Two of the five signals depend on those numbers.

## 26. Journey detail — planned (19 Oct 2026)

Two enhancements requested for routing in **both** Where to Lepak and Where to Eat.

**Planned:** When the travel mode is drive, name the **emptiest carpark** near the venue — its name, available lots and distance — rather than only an aggregate count of lots and carparks.
**Reason:** "598 lots free in 4 carparks" does not tell a driver where to go. The data to do it is already fetched: LTA DataMall returns availability per carpark, and the system already selects those within 500 m. This is presentation of data in hand, not a new source. **Note that parking availability is a live request-time call, not snapshot data** — cached for at most 2 minutes and shared between users because the figures are public and identical for everyone (§3, Data Currency NFR).

**Planned:** When the travel mode is public transport, show **where to board, alight and change** — stop and station names, bus service numbers and the transfer points — rather than only the summary line.
**Reason:** "Walk 4 min → Thomson-East Coast Line → Walk 13 min" tells the user how long but not what to do. OneMap's itinerary already contains the legs, their boarding and alighting stops and the service numbers; the route summary currently discards most of it. Again presentation, not a new source. It also makes the step-by-step directions on the event map genuinely usable rather than merely present.

Both apply to every routed result in Lepak and Eat, and both are additions to existing displays rather than changes to the routing path.

## 25a. Where to Eat — three premises corrected on measurement (19 Oct 2026)

The measurements in `docs/eat-measurements.md` overturned three of §25's premises. §25 stands where it is not contradicted here.

**Retraction — hygiene:** §25 treated NEA hygiene grades as a usable floor. **They are not, and the signal is dropped.** The only open dataset covers June 2015 to September 2016 and was merely re-published in 2024; applying 2016 grades to 2026 venues would be wrong for most of them. Licensing moved from NEA to SFA in 2019, and in January 2026 SFA replaced the A–D scheme with SAFE, whose grades exist only behind a per-establishment search with no dataset, no API and no stated bulk terms. The grade spread was also the opposite of what §25 assumed: A 52.5% and B 46.8% was real spread, while a C/D floor would have hidden 0.7% of places — so the stated reason for making it a filter was wrong as well as the data being unusable.
**Reason this is recorded rather than quietly dropped:** it is the strongest "check the source, not the idea" case in the project. Hygiene grading sounds like the obvious government signal for a food feature, and two independent things — the age of the data and the replacement of the scheme — made it unusable. Both were found by looking, not by reasoning.

**Retraction — Michelin:** §25 proposed a curated Michelin badge. **Not built.** The Guide's terms prohibit automated or manual copying of its pages and the systematic reuse of even small parts of its databases without authorisation, which is exactly what a curated file is. Recorded with its caveat: the site returns an empty HTTP 202 to automated requests, so the terms were read through a search engine's copy rather than the page itself. **The project therefore ships no quality or popularity signal at all**, and says so.

**Decision:** The eighth cuisine group is **Local & Hawker**, replacing Seafood.
**Reason:** Measured on 9,025 OSM food venues: `coffee_shop` (kopitiam) is the single most common cuisine value at 653, and local fare tags together cover 9.7% of all venues, while Seafood covers 1.5% (133). A category list that omits the most common local category while keeping one of the rarest describes OpenStreetMap's tagging conventions rather than how people in Singapore eat.

**Decision:** **No halal or vegetarian filters.**
**Reason:** `diet:halal` covers 3.7% of venues and vegetarian/vegan 3.2%. A halal filter would hide about 96% of places and assert "halal" wherever a volunteer happened to tag it. For a religious requirement that is not a coverage problem but a safety one: the authoritative source is MUIS's certification register, which the project does not hold. Named as future work rather than approximated.

**Decision:** Cuisine and Open now are kept, **with their coverage stated in the interface**: 49.4% of venues carry a cuisine tag (35.5% mapping into the eight groups), and about 21% carry parseable opening hours. Venues with neither are shown and labelled, and listed after those known to be open.
**Reason:** Same rule as unroutable events (§13) and untagged places (§25) — hiding what is unknown deletes most of the dataset while appearing to work.

**Net effect:** of §25's five signals, travel time, price tier and food destinations stand unchanged; cuisine and open-now stand with labelling; hygiene falls. Food destinations are fully supported — 123 operating hawker centres with stall counts (median 45, maximum 226) and 111 photographs — which is why the "destinations as well as eateries" decision now carries more of the feature than it did when it was made.

## 27. Ratings and halal, researched (19 Oct 2026)

Researched after §25a concluded the feature would ship with no quality signal. Two of those conclusions change.

**Finding — Google Places is affordable; the constraint is storage, not cost.** Since March 2025 the $200 monthly credit is replaced by per-SKU free allowances: Essentials 10,000, Pro 5,000 and Enterprise 1,000 events per month. A place's `rating` is a Pro field, so **5,000 free rating lookups a month**, then about US$17 per 1,000. §25's rejection on cost was wrong.

**Decision:** If ratings are built, they are fetched **at request time only, for the venues actually displayed, and never stored**. The ETL may store the **Google place ID**, which Google's Places policies permit to be stored indefinitely; everything else is explicitly barred from caching or storage.
**Reason:** The policy says plainly: "You must not pre-fetch, cache, or store Places API content beyond the allowed exceptions", with the place ID named as the exception. Storing the ID offline and fetching only the rating live keeps us inside the terms while keeping the request cost to one call per displayed venue. It is the same shape as live carpark availability — an External Service with a documented fallback — so the architecture does not change.

**Three consequences recorded with it:** a billing account with a payment card is required even within the free tier; Google's attribution requirements apply (logo, review attributions, a link to Google Maps); and **sorting by rating can only sort within the fetched page**, because unfetched venues have no rating. A sort control must say so rather than implying a global ranking.

**Decision:** Foursquare and Tripadvisor are **rejected**.
**Reason:** Foursquare's ratings are a Premium field at US$18.75 per 1,000 with no free tier. Tripadvisor's Content API permits caching of the location ID only — the same restriction as Google, with none of the free allowance — and is reported to have sunset on 31 August 2026, before this project's demonstration.

**Finding — halal data exists after all, from MUIS rather than OSM.** §25a rejected a halal filter on OSM's 3.7% `diet:halal` coverage. That reasoning holds for OSM, but MUIS publishes its certified establishments through a public search, mirrored by community datasets carrying roughly 4,600 records and attributing MUIS.
**Decision:** If a halal filter is built, it must come from **MUIS certification data, matched strictly on name and postal code, badged with its certification date — never inferred from OSM tags**, and an unmatched venue must read as "not known", never as "not halal".
**Reason:** For a religious requirement the failure modes are not symmetrical: a missing badge inconveniences someone, a wrong badge misleads them about something they cannot compromise on. The same strict-match rule already used for venues (§12) applies with more force here. The terms of the community mirrors are not stated by MUIS, so the source and its retrieval date must be recorded, as for every other curated file.

**Decision:** Where to Eat can be **entered from the other two features**: from a Lepak event ("where to eat near this event") and from the Where to Live recommendation ("where to eat in this neighbourhood").
**Reason:** It needs no new data — the planning area and coordinates of every venue are already computed — and it is what makes three features read as one application rather than three separate tools sharing a menu.
