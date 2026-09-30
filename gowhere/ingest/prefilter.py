"""Regex pre-filter (DECISIONS.md section 3): posts with no date-like text never reach
the LLM. It only has to be generous, not precise: a false positive costs one post's
share of an LLM call, a false negative loses an event."""
import re

_MONTHS = (r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|"
           r"sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?")
_DAYS = r"mon(day)?|tue(s(day)?)?|wed(nesday)?|thu(r(s(day)?)?)?|fri(day)?|sat(urday)?|sun(day)?"
DATE_LIKE = re.compile(
    rf"\b\d{{1,2}}(st|nd|rd|th)?\s*(-|–|to|&)?\s*\d{{0,2}}\s*({_MONTHS})\b"   # 12 Sep, 12 - 13 Sep
    rf"|\b({_MONTHS})\s+\d{{1,2}}\b"                                          # Sep 12
    rf"|\b\d{{1,2}}/\d{{1,2}}(/\d{{2,4}})?\b"                                 # 12/9, 12/09/2026
    rf"|\b\d{{4}}-\d{{2}}-\d{{2}}\b"                                          # 2026-09-12
    rf"|\b({_DAYS})\b"
    rf"|\b(today|tonight|tomorrow|this weekend|now till|now until|daily|every day)\b",
    re.IGNORECASE)


def has_date_like_text(text):
    return bool(DATE_LIKE.search(text or ""))
