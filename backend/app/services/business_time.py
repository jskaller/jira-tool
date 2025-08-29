
from __future__ import annotations
from datetime import datetime, time, timedelta
from typing import Iterable, Set
from zoneinfo import ZoneInfo

WEEKDAY_MAP = {
    'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6
}

def parse_business_days(csv: str) -> Set[int]:
    days = set()
    for part in (csv or "Mon,Tue,Wed,Thu,Fri").split(","):
        p = part.strip()[:3].title()
        if p in WEEKDAY_MAP:
            days.add(WEEKDAY_MAP[p])
    return days or {0,1,2,3,4}

def parse_hhmm(s: str) -> time:
    s = (s or "09:00").strip()
    h, m = s.split(":")
    return time(int(h), int(m))

def business_seconds_between(
    start: datetime,
    end: datetime,
    tz_name: str = "UTC",
    business_start: str = "09:00",
    business_end: str = "17:00",
    business_days_csv: str = "Mon,Tue,Wed,Thu,Fri",
) -> int:
    """
    Compute the number of seconds between start and end that fall within
    business hours (inclusive of business_start, exclusive of business_end)
    on the given business days, in the configured timezone.
    """
    if end <= start:
        return 0

    tz = ZoneInfo(tz_name)
    # Ensure timezone-aware
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    else:
        start = start.astimezone(tz)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)
    else:
        end = end.astimezone(tz)

    bdays = parse_business_days(business_days_csv)
    bstart = parse_hhmm(business_start)
    bend = parse_hhmm(business_end)

    total = 0
    cur = start
    one_day = timedelta(days=1)

    while cur < end:
        day_start = datetime(cur.year, cur.month, cur.day, bstart.hour, bstart.minute, tzinfo=tz)
        day_end = datetime(cur.year, cur.month, cur.day, bend.hour, bend.minute, tzinfo=tz)

        if cur.weekday() in bdays:
            # Overlap of [cur_day_window] with [start,end]
            window_start = max(day_start, start)
            window_end = min(day_end, end)
            if window_end > window_start:
                total += int((window_end - window_start).total_seconds())

        # Move to next day 00:00 to avoid DST pitfalls: jump to midnight then add 1 day
        next_day = (datetime(cur.year, cur.month, cur.day, 0, 0, tzinfo=tz) + one_day)
        if next_day <= cur:  # safety
            next_day = cur + one_day
        cur = next_day

    return total
