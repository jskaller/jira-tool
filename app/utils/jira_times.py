from datetime import datetime, timezone
from typing import Optional

def parse_jira_ts(ts: Optional[str]) -> Optional[datetime]:
    """Parse Jira ISO8601 timestamp (e.g., '2024-10-02T14:05:16.123-0400').
    Returns aware UTC datetime.
    """
    if not ts:
        return None
    # Normalize offsets like -0400 -> -04:00 for fromisoformat
    if len(ts) >= 5 and (ts[-5] in ['+','-']) and ts[-3] != ':':
        ts = ts[:-5] + ts[-5:-2] + ":" + ts[-2:]
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        # Try without milliseconds
        try:
            head, tail = ts.split("T", 1)
            if "." in tail:
                date, rest = tail.split(".", 1)
                # strip until timezone sign
                for i, ch in enumerate(rest):
                    if ch in ['+','-','Z']:
                        rest = rest[i:]
                        break
                ts2 = head + "T" + date + rest
                dt = datetime.fromisoformat(ts2)
            else:
                raise
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
