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
**Reason:** Cost is driven by post volume, not frequency — only unseen posts are processed, so hourly and 6-hourly cost nearly the same (about $5/month on Haiku 4.5 at $1/$5 per million tokens). 6-hourly is chosen for simpler operation. A manual run is available before the demo.

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

Target is 6–10 usable channels; 2 confirmed so far.

## 8. Open items

- 4–8 more Telegram channels to source and verify.
- Division of work between the two of us.
- Sequence diagrams (teammate drafting) — to be reviewed.
- Compile all decisions above into the updated FR/NFR/Data Dictionary/use case document in one pass.

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
