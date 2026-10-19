"""OpenStreetMap `opening_hours`: whether a place is open at a given time.

Only the subset that Singapore food venues actually use is understood (measured
19 Oct 2026, docs/eat-measurements.md): rules separated by ";", each an optional set of
days ("Mo-Fr", "Sa,Su", "Fr-Mo") followed by time spans ("11:00-14:30, 17:30-22:00"),
"off" or "closed", or "24/7". Spans may run past midnight ("18:00-02:00"). As in the
OSM specification, a later rule replaces earlier ones for the days it names.

Anything else, such as months, week numbers, "PH" on its own or free text like
"varies by stall", is not guessed at: the hours count as unknown, and the place is
shown as "Opening hours unknown" rather than open or closed. Public holidays are not
modelled, because we hold no holiday calendar, so "PH" inside a day list is ignored.
"""
import re
from datetime import datetime, time, timedelta

DAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")
_DAY = r"(?:Mo|Tu|We|Th|Fr|Sa|Su|PH)"
_DAY_ITEM = rf"{_DAY}(?:-{_DAY})?"
_DAY_LIST = re.compile(rf"^({_DAY_ITEM}(?:,{_DAY_ITEM})*)\s+(.*)$")
_SPAN = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})(\+?)$")


class Hours:
    """A parsed weekly schedule: for each weekday (0 = Monday), a list of
    (start minute, end minute) spans; an end beyond 1440 runs into the next day."""

    def __init__(self, week):
        self.week = week

    def is_open(self, when):
        """True or False at the naive datetime `when`."""
        return self.span_at(when) is not None

    def span_at(self, when):
        """(start, end) as datetimes of the span covering `when`, or None."""
        minute = when.hour * 60 + when.minute
        day = when.weekday()
        midnight = datetime.combine(when.date(), time(0, 0))
        for start, end in self.week[day]:
            if start <= minute < end:
                return midnight + timedelta(minutes=start), midnight + timedelta(minutes=end)
        for start, end in self.week[(day - 1) % 7]:      # yesterday's late spans
            if end > 1440 and minute < end - 1440:
                return (midnight - timedelta(minutes=1440 - start),
                        midnight + timedelta(minutes=end - 1440))
        return None

    def next_opening(self, when, within_days=7):
        """The datetime the place next opens after `when`, or None if it never does."""
        midnight = datetime.combine(when.date(), time(0, 0))
        for offset in range(within_days + 1):
            day = (when.weekday() + offset) % 7
            for start, _ in sorted(self.week[day]):
                at = midnight + timedelta(days=offset, minutes=start)
                if at > when:
                    return at
        return None


def _days(selector):
    out = set()
    for item in selector.split(","):
        if item == "PH":
            continue                        # public holidays: not modelled
        if "-" in item:
            a, b = item.split("-")
            if "PH" in (a, b):
                return None
            i, j = DAYS.index(a), DAYS.index(b)
            out.update(DAYS[(i + k) % 7] for k in range(((j - i) % 7) + 1))
        else:
            out.add(item)
    return out


def _spans(text):
    spans = []
    for part in text.split(","):
        m = _SPAN.match(part.strip())
        if not m:
            return None
        h1, m1, h2, m2, open_end = m.groups()
        start, end = int(h1) * 60 + int(m1), int(h2) * 60 + int(m2)
        if start > 1440 or end > 1440 + 12 * 60 or int(m1) > 59 or int(m2) > 59:
            return None
        if open_end:                         # "18:00+": open end; assume midnight
            end = max(end, 1440)
        if end <= start:                     # runs past midnight
            end += 1440
        spans.append((start, end))
    return spans


_RULE_START = re.compile(rf",\s*(?={_DAY}[\s,-])")
_COMPLETE = re.compile(r"\d:\d\d|\boff\b|\bclosed\b|24/7")


def _comma_rules(rule):
    """"Mo-Fr 07:30-19:30, Sa 07:30-14:00, Su off" is three rules joined by commas.
    A comma before a day name starts a new rule only once the text so far has its
    times, so the day list in "Sa,Su 10:00-22:00" is left whole."""
    parts, current = [], ""
    for piece in _RULE_START.split(rule):
        current = f"{current},{piece}" if current else piece
        if _COMPLETE.search(current):
            parts.append(current.strip())
            current = ""
    if current:
        parts.append(current.strip())
    return parts


def parse(text):
    """Hours, or None when the value is missing or outside the understood subset."""
    if not text or not text.strip():
        return None
    week = {d: [] for d in range(7)}
    rules = [r.strip() for r in text.strip().rstrip(";").split(";")]
    if not rules or any(not r for r in rules):
        return None
    rules = [part for r in rules for part in _comma_rules(r)]
    for rule in rules:
        m = _DAY_LIST.match(rule)
        if m:
            days, body = _days(m.group(1)), m.group(2).strip()
            if days is None:
                return None
            if not days:                     # a "PH ..." rule on its own
                continue
        else:
            days, body = set(DAYS), rule
        if body == "24/7":
            spans = [(0, 1440)]
        elif body in ("off", "closed"):
            spans = []
        else:
            spans = _spans(body)
            if spans is None:
                return None
        for d in days:
            week[DAYS.index(d)] = list(spans)
    return Hours(week)


def clock(dt):
    """'9 am', '10:30 pm', 'midnight'."""
    if dt.hour == 0 and dt.minute == 0:
        return "midnight"
    return f"{dt.hour % 12 or 12}{f':{dt:%M}' if dt.minute else ''} {'am' if dt.hour < 12 else 'pm'}"


def status(text, when):
    """{open: True/False/None, text} for a place's `opening_hours` at `when`.
    None means unknown: the hours are missing or not understood."""
    hours = parse(text)
    if hours is None:
        return {"open": None, "text": "Opening hours unknown"}
    span = hours.span_at(when)
    if span is not None:
        start, end = span
        if end - start >= timedelta(hours=24):
            return {"open": True, "text": "Open 24 hours"}
        return {"open": True, "text": f"Open until {clock(end)}"}
    nxt = hours.next_opening(when)
    if nxt is None:
        return {"open": False, "text": "Closed"}
    if nxt.date() == when.date():
        return {"open": False, "text": f"Closed, opens {clock(nxt)}"}
    if nxt.date() == when.date() + timedelta(days=1):
        return {"open": False, "text": f"Closed, opens tomorrow {clock(nxt)}"}
    return {"open": False, "text": f"Closed, opens {nxt:%a} {clock(nxt)}"}
