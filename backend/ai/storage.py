"""Small JSONL persistence for AI records in a backend with no existing database.

Each write retains source and full spatial/depth resolution so later analytics can
query historical sensor and model records without rerunning inference.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "ai"
PREDICTIONS_FILE = DATA_DIR / "soil_moisture_predictions.jsonl"
SENSOR_FILE = DATA_DIR / "soil_moisture_sensor_readings.jsonl"
FIELD_CONFIG_FILE = DATA_DIR / "field_configurations.json"


def append_record(path: Path, record: Dict[str, Any]) -> None:
    """Append one source-discriminated record to *path* as a JSONL row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


def save_field_configuration(field_id: str, configuration: Dict[str, Any]) -> None:
    """Persist the configured field context used by future AI resolution."""
    FIELD_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: Dict[str, Dict[str, Any]] = {}
    if FIELD_CONFIG_FILE.exists():
        try:
            existing = json.loads(FIELD_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing[field_id] = configuration
    FIELD_CONFIG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def load_field_configuration(field_id: str) -> Optional[Dict[str, Any]]:
    """Return a persisted field configuration, if one has been saved."""
    if not FIELD_CONFIG_FILE.exists():
        return None
    try:
        return json.loads(FIELD_CONFIG_FILE.read_text(encoding="utf-8")).get(field_id)
    except (json.JSONDecodeError, OSError):
        return None


def query_predictions(field_id: str, start: Optional[str] = None, end: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read stored predictions for *field_id*, optionally constrained by ISO timestamps."""
    if not PREDICTIONS_FILE.exists():
        return []
    results = []
    for line in PREDICTIONS_FILE.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        timestamp = record["timestamp"]
        if record.get("field_id") == field_id and (start is None or timestamp >= start) and (end is None or timestamp <= end):
            results.append(record)
    return results
