"""Content-addressed GPX imports. Private data never belongs in the web app."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from defusedxml import ElementTree as SafeXML

MAX_BYTES = 25 * 1024 * 1024
MAX_POINTS = 250_000
POINT_COLUMNS = ["ride_id", "track_segment", "point_index", "timestamp_utc", "latitude", "longitude", "elevation"]


def utc_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


@contextmanager
def connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS imports (
            ride_id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL, point_count INTEGER NOT NULL,
            details TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS points (
            ride_id TEXT NOT NULL REFERENCES imports(ride_id),
            track_segment INTEGER NOT NULL, point_index INTEGER NOT NULL,
            timestamp_utc TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
            elevation REAL, PRIMARY KEY(ride_id, track_segment, point_index)
        );
        """)
        with db:
            yield db
    finally:
        db.close()


def parse_gpx(data: bytes, ride_id: str) -> tuple[list[dict], dict]:
    if len(data) > MAX_BYTES:
        raise ValueError("file_too_large")
    root = SafeXML.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    if root.tag.split("}")[-1] != "gpx":
        raise ValueError("not_gpx")
    namespace = root.tag[:-3] if root.tag.startswith("{") else ""
    points = []
    segment_count = 0
    for track in root.findall(f"{namespace}trk"):
        for segment in track.findall(f"{namespace}trkseg"):
            for index, element in enumerate(segment.findall(f"{namespace}trkpt")):
                if len(points) >= MAX_POINTS:
                    raise ValueError("too_many_points")
                lat, lon = float(element.attrib["lat"]), float(element.attrib["lon"])
                elevation_text = element.findtext(f"{namespace}ele")
                elevation = float(elevation_text) if elevation_text else None
                if not all(math.isfinite(v) for v in (lat, lon)) or (elevation is not None and not math.isfinite(elevation)):
                    raise ValueError("non_finite_coordinate_or_elevation")
                points.append(dict(zip(POINT_COLUMNS, [ride_id, segment_count, index,
                    utc_time(element.findtext(f"{namespace}time")), lat, lon, elevation])))
            segment_count += 1
    if not points:
        raise ValueError("no_track_points")
    timed = sum(p["timestamp_utc"] is not None for p in points)
    gaps = []
    for a, b in zip(points, points[1:]):
        if a["track_segment"] == b["track_segment"] and a["timestamp_utc"] and b["timestamp_utc"]:
            gaps.append((datetime.fromisoformat(b["timestamp_utc"]) - datetime.fromisoformat(a["timestamp_utc"])).total_seconds())
    warnings = []
    if timed < len(points):
        warnings.append("missing_or_invalid_timestamps")
    if not timed:
        warnings.append("no_usable_timestamps")
    return points, {"segments": segment_count, "timed_points": timed,
        "elevation_points": sum(p["elevation"] is not None for p in points),
        "sampling_seconds_min": min(gaps) if gaps else None,
        "sampling_seconds_max": max(gaps) if gaps else None, "warnings": warnings}


def import_directory(directory: Path, database: Path, manifests: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("Input must be an existing directory")
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".gpx")
    if not files:
        raise ValueError("No GPX files found in directory")
    results = []
    with connect(database) as db:
        for file in files:
            # Hash in bounded chunks even for rejected oversized files.
            hasher = hashlib.sha256()
            with file.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
            ride_id = "ride_" + digest
            existing = db.execute("SELECT * FROM imports WHERE sha256=?", (digest,)).fetchone()
            if existing:
                results.append({"filename": file.name, "ride_id": existing["ride_id"], "sha256": digest,
                    "status": existing["status"], "duplicate": True, "point_count": existing["point_count"],
                    "details": json.loads(existing["details"])})
                continue
            points, details, status = [], {}, "imported"
            try:
                with file.open("rb") as handle:
                    data = handle.read(MAX_BYTES + 1)
                if hashlib.sha256(data).hexdigest() != digest and len(data) <= MAX_BYTES:
                    raise ValueError("file_changed_during_import")
                points, details = parse_gpx(data, ride_id)
            except Exception as error:
                status = "rejected"
                details = {"error": type(error).__name__, "reason": str(error)[:200]}
            with db:
                db.execute("INSERT INTO imports VALUES (?,?,?,?,?)", (ride_id, digest, status, len(points), json.dumps(details)))
                db.executemany("INSERT INTO points VALUES (?,?,?,?,?,?,?)", [tuple(p[k] for k in POINT_COLUMNS) for p in points])
            results.append({"filename": file.name, "ride_id": ride_id, "sha256": digest,
                "status": status, "duplicate": False, "point_count": len(points), "details": details})
    manifest = {"schema_version": 1, "run_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(), "files": results}
    manifests.mkdir(parents=True, exist_ok=True)
    (manifests / f'{manifest["run_id"]}.json').write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_points(database: Path) -> list[dict]:
    with connect(database) as db:
        return [dict(row) for row in db.execute("SELECT * FROM points ORDER BY ride_id, track_segment, point_index")]
