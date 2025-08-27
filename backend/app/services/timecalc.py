from datetime import datetime, timedelta, time
from typing import Tuple

WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

def parse_hhmm(s: str) -> time:
    hh, mm = s.split(':')
    return time(int(hh), int(mm))

def business_duration(start: datetime, end: datetime, bh_start: str='09:00', bh_end: str='17:00', business_days: str='Mon,Tue,Wed,Thu,Fri') -> timedelta:
    """Compute business-hours duration between two timestamps (inclusive of start, exclusive of end).
    Simple and efficient clipping by day windows; ignores holidays for v1.
    """
    if end <= start:
        return timedelta(0)
    bstart = parse_hhmm(bh_start)
    bend = parse_hhmm(bh_end)
    days = set(d.strip() for d in business_days.split(','))
    cur = start
    total = timedelta(0)
    # Iterate by day boundaries
    while cur.date() <= end.date():
        day_start = datetime.combine(cur.date(), bstart, tzinfo=start.tzinfo)
        day_end = datetime.combine(cur.date(), bend, tzinfo=start.tzinfo)
        wd = WEEKDAYS[day_start.weekday()]
        if wd in days:
            seg_start = max(cur, day_start)
            seg_end = min(end, day_end)
            if seg_end > seg_start:
                total += (seg_end - seg_start)
        cur = datetime.combine((cur + timedelta(days=1)).date(), bstart, tzinfo=start.tzinfo)
    return total
