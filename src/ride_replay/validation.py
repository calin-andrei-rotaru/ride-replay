"""Private evidence and staging for a real-data run; never clears publication."""
import hashlib
import json
import math
import statistics
import uuid
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path

from .ingest import connect, load_points
from .matching import detect_efforts, seconds, validate_segment
from .snapshot import build_snapshot, write_json


def inspect_rides(database: Path) -> list[dict]:
    if not database.is_file():
        raise ValueError("Import rides before inspecting the database")
    output = []
    for ride_id, group in groupby(load_points(database), key=lambda p: p["ride_id"]):
        points = list(group)
        times = [p["timestamp_utc"] for p in points if p["timestamp_utc"]]
        intervals = [seconds(b["timestamp_utc"]) - seconds(a["timestamp_utc"])
            for a, b in zip(points, points[1:]) if a["track_segment"] == b["track_segment"] and a["timestamp_utc"] and b["timestamp_utc"]]
        positive = sorted(v for v in intervals if v > 0)
        output.append({"ride_id": ride_id, "point_count": len(points),
            "track_segments": len({p["track_segment"] for p in points}),
            "missing_timestamps": sum(not p["timestamp_utc"] for p in points),
            "elevation_points": sum(p["elevation"] is not None for p in points),
            "invalid_coordinates": sum(not (-90 <= p["latitude"] <= 90 and -180 <= p["longitude"] <= 180) for p in points),
            "non_increasing_time_edges": sum(v <= 0 for v in intervals),
            "first_timestamp": min(times, key=seconds) if times else None,
            "last_timestamp": max(times, key=seconds) if times else None,
            "sampling_seconds_median": statistics.median(positive) if positive else None,
            "sampling_seconds_p95": positive[math.ceil(.95 * len(positive)) - 1] if positive else None,
            "sampling_seconds_max": max(positive) if positive else None})
    return output


def segment_from_indices(database: Path, ride_id: str, track_segment: int, indices: list[int], label: str) -> dict:
    if not database.is_file():
        raise ValueError("Import rides before selecting a climb")
    if len(indices) != 3 or not (0 <= indices[0] < indices[1] < indices[2]):
        raise ValueError("Choose ordered start < checkpoint < finish point indices")
    points = {p["point_index"]: p for p in load_points(database) if p["ride_id"] == ride_id and p["track_segment"] == track_segment}
    if not all(index in points for index in indices):
        raise ValueError("Selected points must exist in one source track segment")
    segment = {"label": label}
    for name, index in zip(("start", "checkpoint", "finish"), indices):
        point = points[index]
        segment[name] = [point["latitude"], point["longitude"]]
    return validate_segment(segment)


def assert_effort_parity(expected: list[dict], actual: list[dict]):
    def key(row):
        return (row["ride_id"], row["track_segment"], row["start_index"], row["finish_index"])
    expected, actual = sorted(expected, key=key), sorted(actual, key=key)
    if len(expected) != len(actual):
        raise ValueError("Cloud/local effort counts differ")
    for a, b in zip(expected, actual):
        if key(a) != key(b) or a["accepted"] != b["accepted"] or a["started_at"] != b["started_at"] or sorted(a["quality_reasons"]) != sorted(b["quality_reasons"]):
            raise ValueError("Cloud/local effort identity or quality differs")
        left, right = a["elapsed_seconds"], b["elapsed_seconds"]
        if (left is None) != (right is None) or (left is not None and not math.isclose(left, right, rel_tol=0, abs_tol=1e-6)):
            raise ValueError("Cloud/local elapsed times differ")


def prepare_run(database: Path, segment_path: Path, ride_ids: list[str], output: Path, data_kind: str) -> dict:
    if data_kind not in ("real", "synthetic"):
        raise ValueError("Declare whether input data is real or synthetic")
    if len(set(ride_ids)) < 2:
        raise ValueError("Select at least two distinct imported rides")
    if not database.is_file():
        raise ValueError("Import rides before preparing a run")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose a new empty run directory to preserve earlier evidence")
    segment = validate_segment(json.loads(segment_path.read_text(encoding="utf-8")))
    selected = set(ride_ids)
    points = [p for p in load_points(database) if p["ride_id"] in selected]
    if {p["ride_id"] for p in points} != selected:
        raise ValueError("Every selected ride must exist and have imported points")
    efforts = detect_efforts(points, segment)
    accepted = [e for e in efforts if e["accepted"]]
    if len({e["ride_id"] for e in accepted}) < 2:
        raise ValueError("At least two selected rides need an accepted passage; inspect tracks and matching thresholds first")
    created = datetime.now(timezone.utc).isoformat()
    with connect(database) as db:
        records = [dict(row) for row in db.execute("SELECT * FROM imports ORDER BY ride_id") if row["ride_id"] in selected]
    for record in records:
        record["details"] = json.loads(record["details"])
    inputs = output / "input"
    write_json(inputs / "bronze.json", points)
    write_json(inputs / "segment.json", segment)
    write_json(inputs / "expected-efforts.json", efforts)
    write_json(inputs / "manifests" / "selected.json", {"run_id": uuid.uuid4().hex, "created_at": created,
        "manifest_kind": "validation_selection", "files": records})
    review = [{"ride_id": e["ride_id"], "track_segment": e["track_segment"],
        "start_index": e["start_index"], "finish_index": e["finish_index"],
        "started_at": e["started_at"], "elapsed_seconds": e["elapsed_seconds"],
        "reviewed_against_source": False, "notes": ""} for e in accepted]
    write_json(output / "manual-checks.json", review)
    # Selection is approved for this loopback preview only. No publication
    # approval file is created and the tracked public snapshot is untouched.
    preview = build_snapshot(efforts, {"data_kind": data_kind, "approved_ride_ids": ride_ids}, segment["label"])
    write_json(output / "preview" / "snapshot.json", preview)
    report = {"schema_version": 1, "prepared_at": created, "declared_data_kind": data_kind,
        "real_data_verified": False, "publication_approved": False, "databricks_run_verified": False,
        "point_count": len(points), "accepted_efforts": len(accepted),
        "rejected_efforts": len(efforts) - len(accepted),
        "bronze_sha256": hashlib.sha256((inputs / "bronze.json").read_bytes()).hexdigest(),
        "segment_sha256": hashlib.sha256((inputs / "segment.json").read_bytes()).hexdigest(),
        "rides": [r for r in inspect_rides(database) if r["ride_id"] in selected]}
    write_json(output / "validation.json", report)
    return {"output": str(output), "declared_data_kind": data_kind, "rides": len(selected),
        "points": len(points), "accepted": len(accepted), "rejected": len(efforts) - len(accepted),
        "publication_approved": False, "manual_review": str(output / "manual-checks.json")}
