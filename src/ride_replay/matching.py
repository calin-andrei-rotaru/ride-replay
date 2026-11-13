"""Shared local/Spark quality checks and directed geofence matching."""
from __future__ import annotations

import math
from datetime import datetime
from itertools import groupby


def distance(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    value = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1, max(0, value))))


def seconds(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() if value else None


def validate_segment(segment: dict) -> dict:
    if not isinstance(segment.get("label"), str) or not segment["label"].strip():
        raise ValueError("Segment needs a public label")
    for name in ("start", "checkpoint", "finish"):
        coords = segment[name]
        if len(coords) != 2 or not (-90 <= coords[0] <= 90 and -180 <= coords[1] <= 180):
            raise ValueError(f"Invalid {name} coordinates")
    for key, default in (("radius_m", 35), ("max_gap_seconds", 30), ("max_speed_mps", 25), ("min_points", 5), ("max_effort_seconds", 3600)):
        segment.setdefault(key, default)
        if not math.isfinite(segment[key]) or segment[key] <= 0:
            raise ValueError(f"Invalid {key}")
    if segment["min_points"] < 3 or int(segment["min_points"]) != segment["min_points"]:
        raise ValueError("min_points must be an integer >= 3")
    for a, b in (("start", "checkpoint"), ("checkpoint", "finish"), ("start", "finish")):
        if distance(segment[a], segment[b]) <= 2 * segment["radius_m"]:
            raise ValueError("Geofences must not overlap")
    return segment


def silver_points(points: list[dict], segment: dict) -> list[dict]:
    output = []
    previous = None
    for p in sorted(points, key=lambda p: (p["ride_id"], p["track_segment"], p["point_index"])):
        flags = []
        valid = -90 <= p["latitude"] <= 90 and -180 <= p["longitude"] <= 180
        if not valid:
            flags.append("invalid_coordinate")
        if p["timestamp_utc"] is None:
            flags.append("missing_timestamp")
        edge_flags = []
        if previous and (p["ride_id"], p["track_segment"]) == (previous["ride_id"], previous["track_segment"]):
            if p["timestamp_utc"] and previous["timestamp_utc"]:
                dt = seconds(p["timestamp_utc"]) - seconds(previous["timestamp_utc"])
                if dt <= 0:
                    edge_flags.append("non_increasing_timestamp")
                elif dt > segment["max_gap_seconds"]:
                    edge_flags.append("sampling_gap")
                if dt > 0 and distance((p["latitude"], p["longitude"]), (previous["latitude"], previous["longitude"])) / dt > segment["max_speed_mps"]:
                    edge_flags.append("gps_jump")
            else:
                edge_flags.append("missing_timestamp")
        output.append({**p, "quality_flags": flags, "edge_flags": edge_flags})
        previous = p
    return output


def detect_efforts(points: list[dict], segment: dict) -> list[dict]:
    segment = validate_segment(dict(segment))
    clean = silver_points(points, segment)
    efforts = []

    def record(path, reason=None, checkpoint=False):
        flags = {flag for p in path for flag in p["quality_flags"]}
        flags.update(flag for p in path[1:] for flag in p["edge_flags"])
        if reason:
            flags.add(reason)
        if not checkpoint:
            flags.add("missing_checkpoint")
        if len(path) < segment["min_points"]:
            flags.add("insufficient_sampling")
        start, finish = path[0], path[-1]
        elapsed = seconds(finish["timestamp_utc"]) - seconds(start["timestamp_utc"]) if start["timestamp_utc"] and finish["timestamp_utc"] else None
        if elapsed is not None and (elapsed <= 0 or elapsed > segment["max_effort_seconds"]):
            flags.add("invalid_duration")
        efforts.append({"ride_id": start["ride_id"], "track_segment": start["track_segment"],
            "start_index": start["point_index"], "finish_index": finish["point_index"],
            "started_at": start["timestamp_utc"], "elapsed_seconds": elapsed,
            "accepted": not flags, "quality_reasons": sorted(flags)})

    for _, group in groupby(clean, key=lambda p: (p["ride_id"], p["track_segment"])):
        active, checkpoint, reverse, reverse_checkpoint = [], False, [], False
        previous_zones = set()
        for point in group:
            zones = {name for name in ("start", "checkpoint", "finish")
                if "invalid_coordinate" not in point["quality_flags"] and distance((point["latitude"], point["longitude"]), segment[name]) <= segment["radius_m"]}
            entered = zones - previous_zones
            if active:
                active.append(point)
            if reverse:
                reverse.append(point)
            if "start" in entered:
                reversed_pass = bool(reverse and reverse_checkpoint)
                if reversed_pass:
                    record(reverse, "reverse_direction", True)
                reverse, reverse_checkpoint = [], False
                if active:
                    record(active, "restarted_before_finish", checkpoint)
                active, checkpoint = ([] if reversed_pass else [point]), False
            if "checkpoint" in entered:
                if active:
                    checkpoint = True
                if reverse:
                    reverse_checkpoint = True
            if "finish" in entered:
                if active:
                    record(active, checkpoint=checkpoint)
                    active, checkpoint = [], False
                else:
                    reverse, reverse_checkpoint = [point], False
            previous_zones = zones
        if active:
            record(active, "incomplete_pass", checkpoint)
    return efforts
