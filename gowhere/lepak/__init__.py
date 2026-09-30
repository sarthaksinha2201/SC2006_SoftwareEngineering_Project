from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))


def sgt_now():
    """The current Singapore time as a naive datetime, the form the event store uses."""
    return datetime.now(SGT).replace(tzinfo=None, second=0, microsecond=0)
