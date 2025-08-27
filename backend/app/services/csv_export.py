from typing import Iterable, Dict, Any
from fastapi import Response
import csv
from io import StringIO

def stream_csv(rows: Iterable[Dict[str, Any]], filename: str) -> Response:
    sio = StringIO()
    if rows:
        # Ensure iteration twice; small mock, so fine
        rows = list(rows)
        fieldnames = sorted(set().union(*[r.keys() for r in rows]))
        writer = csv.DictWriter(sio, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    else:
        sio.write("empty\n")
    resp = Response(content=sio.getvalue(), media_type="text/csv")
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
