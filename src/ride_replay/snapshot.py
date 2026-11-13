"""Explicit publication allowlist. Construct fields, never redact a private object."""
import json
import math
from datetime import datetime
from pathlib import Path


def build_snapshot(efforts: list[dict], approval: dict, public_label: str) -> dict:
    if approval.get("data_kind") not in ("synthetic", "real"):
        raise ValueError("Approval must declare data_kind: synthetic or real")
    allowed = approval.get("approved_ride_ids")
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) for x in allowed):
        raise ValueError("An explicit nonempty approved_ride_ids allowlist is required")
    selected = [e for e in efforts if e["ride_id"] in set(allowed)]
    accepted = sorted((e for e in selected if e["accepted"]), key=lambda e: (
        datetime.fromisoformat(e["started_at"].replace("Z", "+00:00")), e["ride_id"], e["start_index"]))
    snapshot = {"schema_version": 1, "data_kind": approval["data_kind"], "segments": [{
        "label": public_label,
        "efforts": [{"order": index + 1, "duration_seconds": math.floor(e["elapsed_seconds"] + 0.5)} for index, e in enumerate(accepted)],
        "counts": {"rides": len({e["ride_id"] for e in selected}), "accepted": len(accepted),
            "rejected": sum(not e["accepted"] for e in selected)}
    }]}
    validate_public_snapshot(snapshot)
    return snapshot


def validate_public_snapshot(snapshot: dict) -> None:
    if set(snapshot) != {"schema_version", "data_kind", "segments"} or snapshot["schema_version"] != 1 or snapshot["data_kind"] not in ("synthetic", "real"):
        raise ValueError("Invalid public snapshot envelope")
    for segment in snapshot["segments"]:
        if set(segment) != {"label", "efforts", "counts"} or not isinstance(segment["label"], str):
            raise ValueError("Unexpected public segment fields")
        if set(segment["counts"]) != {"rides", "accepted", "rejected"}:
            raise ValueError("Unexpected count fields")
        if any(type(v) is not int or v < 0 for v in segment["counts"].values()):
            raise ValueError("Invalid count")
        for index, effort in enumerate(segment["efforts"], 1):
            if set(effort) != {"order", "duration_seconds"} or effort["order"] != index or type(effort["duration_seconds"]) is not int or effort["duration_seconds"] <= 0:
                raise ValueError("Invalid public effort")
        if segment["counts"]["accepted"] != len(segment["efforts"]):
            raise ValueError("Inconsistent accepted count")


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
