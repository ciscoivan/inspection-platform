import json
import sys
from pathlib import Path

# Point to the parent project's inspection.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import inspection as insp


def run_single_device(device_info: dict) -> dict:
    """Run inspection on a single device. Blocking — run in thread pool."""
    result = insp.inspect_device(device_info)
    if "sections" in result:
        result["raw_data"] = json.dumps(result["sections"], ensure_ascii=False)
    return result
