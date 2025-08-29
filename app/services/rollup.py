from typing import Dict, Any, List

def build_rollups(issues: List[dict]) -> Dict[str, Any]:
    return {"issue_count": len(issues)}
