from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Set

def _parse_hhmm(s: str) -> time:
    hh, mm = s.split(":")
    return time(hour=int(hh), minute=int(mm))

def business_seconds_between(start: datetime, end: datetime, tz: str, day_start: str, day_end: str, days_csv: str) -> int:
    if end <= start:
        return 0
    tzinfo = ZoneInfo(tz)
    start = start.astimezone(tzinfo)
    end = end.astimezone(tzinfo)
    bh_start = _parse_hhmm(day_start)
    bh_end = _parse_hhmm(day_end)
    days: Set[str] = set(x.strip() for x in days_csv.split(",") if x.strip())

    cur = start
    total = 0
    while cur < end:
        cur_date = cur.date()
        weekday = cur.strftime("%a")
        window_start = datetime.combine(cur_date, bh_start, tzinfo)
        window_end = datetime.combine(cur_date, bh_end, tzinfo)
        next_midnight = datetime.combine(cur_date, time(0,0), tzinfo) + timedelta(days=1)
        if weekday in days:
            s = max(cur, window_start)
            e = min(end, window_end)
            if e > s:
                total += int((e - s).total_seconds())
        cur = next_midnight
    return total
