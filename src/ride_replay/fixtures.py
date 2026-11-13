"""Generate synthetic tracks locally; these are never claimed to be real rides."""
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from .ingest import import_directory
from .matching import detect_efforts
from .ingest import load_points
from .snapshot import build_snapshot, write_json

DEMO_SEGMENT = {"label": "The observatory climb · synthetic", "start": [47.17, 27.55],
    "checkpoint": [47.175, 27.55], "finish": [47.18, 27.55],
    "radius_m": 35, "max_gap_seconds": 30, "max_speed_mps": 25, "min_points": 5, "max_effort_seconds": 3600}


def make_gpx(duration=420, day=1, reverse=False, near_miss=False, gap=False, split=False, timestamps=True):
    root = Element("gpx", {"version": "1.1", "creator": "Ride Replay SYNTHETIC fixture", "xmlns": "http://www.topografix.com/GPX/1/1"})
    track = SubElement(root, "trk")
    segment = SubElement(track, "trkseg")
    start = datetime(2026, 1, day, 8, tzinfo=timezone.utc)
    # 51 samples: 6.7–9.2 seconds apart in the normal demo.
    for index in range(51):
        if split and index == 25:
            segment = SubElement(track, "trkseg")
        fraction = index / 50
        latitude = 47.17 + (1-fraction if reverse else fraction) * .01
        longitude = 27.55 + (.002 * math.sin(math.pi * fraction) if near_miss else 0)
        point = SubElement(segment, "trkpt", {"lat": f"{latitude:.6f}", "lon": f"{longitude:.6f}"})
        SubElement(point, "ele").text = str(round(80 + fraction * 65, 2))
        if timestamps:
            offset = duration * fraction + (90 if gap and index >= 25 else 0)
            SubElement(point, "time").text = (start + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")
    return tostring(root, encoding="utf-8", xml_declaration=True)


def generate_demo(workspace: Path, output: Path):
    rides = workspace / "rides"
    rides.mkdir(parents=True, exist_ok=True)
    durations = [490, 474, 481, 453, 460, 435, 442, 418, 426, 403, 394, 379]
    for i, duration in enumerate(durations, 1):
        (rides / f"synthetic-{i:02}.gpx").write_bytes(make_gpx(duration, i))
    for i, kwargs in enumerate(({"near_miss": True}, {"gap": True}, {"reverse": True}), 13):
        (rides / f"synthetic-{i:02}.gpx").write_bytes(make_gpx(day=i, **kwargs))
    manifest = import_directory(rides, workspace / "rides.sqlite", workspace / "manifests")
    efforts = detect_efforts(load_points(workspace / "rides.sqlite"), DEMO_SEGMENT)
    approval = {"data_kind": "synthetic", "approved_ride_ids": [r["ride_id"] for r in manifest["files"]]}
    efforts = [e for e in efforts if e["ride_id"] in approval["approved_ride_ids"]]
    write_json(workspace / "segment.json", DEMO_SEGMENT)
    write_json(workspace / "approval.json", approval)
    write_json(workspace / "efforts.json", efforts)
    write_json(output, build_snapshot(efforts, approval, DEMO_SEGMENT["label"]))
    return {"data_kind": "synthetic", "files": len(manifest["files"]), "accepted": sum(e["accepted"] for e in efforts), "rejected": sum(not e["accepted"] for e in efforts)}
