import json
import sqlite3
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ride_replay.fixtures import DEMO_SEGMENT, generate_demo, make_gpx
from ride_replay.ingest import MAX_BYTES, connect, import_directory, parse_gpx
from ride_replay.matching import detect_efforts, silver_points, validate_segment
from ride_replay.snapshot import build_snapshot, validate_public_snapshot
from ride_replay.strava import streams_to_gpx, sync_strava


def points(**kwargs):
    return parse_gpx(make_gpx(**kwargs), "private-ride-id")[0]


def test_repeat_import_stable_and_manifest(tmp_path):
    (tmp_path / "ride.gpx").write_bytes(make_gpx())
    first = import_directory(tmp_path, tmp_path / "rides.db", tmp_path / "runs")
    (tmp_path / "renamed.GPX").write_bytes(make_gpx())
    second = import_directory(tmp_path, tmp_path / "rides.db", tmp_path / "runs")
    assert all(f["duplicate"] for f in second["files"])
    assert len({f["ride_id"] for f in first["files"] + second["files"]}) == 1
    with connect(tmp_path / "rides.db") as db:
        assert db.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM points").fetchone()[0] == 51
    assert len(list((tmp_path / "runs").glob("*.json"))) == 2


def test_database_context_releases_file(tmp_path):
    path = tmp_path / "rides.db"
    with connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM points").fetchone()[0] == 0
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")
    path.rename(tmp_path / "moved.db")


def test_forward_manual_crossings():
    effort, = detect_efforts(points(), DEMO_SEGMENT)
    assert effort["accepted"]
    assert effort["start_index"] == 0
    assert effort["finish_index"] == 49
    assert effort["elapsed_seconds"] == pytest.approx(411.6)


@pytest.mark.parametrize("options,reason", [
    ({"reverse": True}, "reverse_direction"),
    ({"near_miss": True}, "missing_checkpoint"),
    ({"gap": True}, "sampling_gap"),
    ({"split": True}, "incomplete_pass"),
    ({"timestamps": False}, "missing_timestamp"),
])
def test_rejections(options, reason):
    efforts = detect_efforts(points(**options), DEMO_SEGMENT)
    assert not any(e["accepted"] for e in efforts)
    assert any(reason in e["quality_reasons"] for e in efforts)


def test_repeated_passes():
    from datetime import datetime, timedelta
    first = points()
    second = points()
    for p in second:
        p["point_index"] += len(first)
        p["timestamp_utc"] = (datetime.fromisoformat(p["timestamp_utc"]) + timedelta(seconds=600)).isoformat()
    efforts = detect_efforts(first + second, DEMO_SEGMENT)
    assert sum(e["accepted"] for e in efforts) == 2


def test_near_miss_is_plausible_and_reverse_is_one_candidate():
    effort, = detect_efforts(points(near_miss=True), DEMO_SEGMENT)
    assert effort["quality_reasons"] == ["missing_checkpoint"]
    effort, = detect_efforts(points(reverse=True), DEMO_SEGMENT)
    assert effort["quality_reasons"] == ["reverse_direction"]


def test_jump_backwards_time_invalid_coordinates_and_sparse():
    for mutation, reason in ((lambda p: p[20].update(longitude=28), "gps_jump"),
        (lambda p: p[20].update(timestamp_utc=p[19]["timestamp_utc"]), "non_increasing_timestamp"),
        (lambda p: p[20].update(latitude=91), "invalid_coordinate")):
        p = points()
        mutation(p)
        effort, = detect_efforts(p, DEMO_SEGMENT)
        assert not effort["accepted"] and reason in effort["quality_reasons"]
    sparse = [points()[i] for i in (0, 25, 50)]
    assert "insufficient_sampling" in detect_efforts(sparse, DEMO_SEGMENT)[0]["quality_reasons"]


def test_segment_boundaries_do_not_flag_cross_segment_edges():
    p = points(split=True)
    silver = silver_points(p, DEMO_SEGMENT)
    assert silver[25]["edge_flags"] == []
    assert not any(e["accepted"] for e in detect_efforts(p, DEMO_SEGMENT))


def test_xml_security_and_limits(tmp_path):
    attacks = [b'<gpx><broken>', b'<!DOCTYPE gpx [<!ENTITY x SYSTEM "file:///etc/passwd">]><gpx>&x;</gpx>', b'<gpx/>', b'<notgpx/>', b'x' * (MAX_BYTES + 1)]
    for attack in attacks:
        with pytest.raises(Exception):
            parse_gpx(attack, "x")
    (tmp_path / "broken.gpx").write_bytes(attacks[0])
    result = import_directory(tmp_path, tmp_path / "rides.db", tmp_path / "runs")
    assert result["files"][0]["status"] == "rejected"
    assert result["files"][0]["point_count"] == 0


def test_timezone_and_no_timestamp_contract():
    xml = make_gpx().replace(b'2026-01-01T08:00:00Z', b'2026-01-01T10:00:00+02:00')
    parsed, details = parse_gpx(xml, "x")
    assert parsed[0]["timestamp_utc"] == "2026-01-01T08:00:00Z"
    assert details["timed_points"] == 51
    _, details = parse_gpx(make_gpx(timestamps=False), "x")
    assert "no_usable_timestamps" in details["warnings"]


def test_export_explicit_allowlist_and_field_whitelist():
    efforts = detect_efforts(points(), DEMO_SEGMENT)
    result = build_snapshot(efforts, {"approved_ride_ids": ["private-ride-id"], "data_kind": "synthetic"}, "Public climb")
    assert result["segments"][0]["efforts"] == [{"order": 1, "duration_seconds": 412}]
    assert "private-ride-id" not in json.dumps(result)
    assert "2026-" not in json.dumps(result)
    assert "latitude" not in json.dumps(result)
    other = build_snapshot(efforts, {"approved_ride_ids": ["different"], "data_kind": "real"}, "Public climb")
    assert not other["segments"][0]["efforts"]
    with pytest.raises(ValueError):
        build_snapshot(efforts, {"approved_ride_ids": [], "data_kind": "real"}, "Public climb")
    result["segments"][0]["ride_id"] = "private"
    with pytest.raises(ValueError):
        validate_public_snapshot(result)


def test_export_orders_fractional_timestamp_after_whole_second():
    base, = detect_efforts(points(), DEMO_SEGMENT)
    efforts = [{**base, "started_at": "2026-01-01T08:00:00.500000Z", "elapsed_seconds": 400},
        {**base, "started_at": "2026-01-01T08:00:00Z", "elapsed_seconds": 420}]
    result = build_snapshot(efforts, {"data_kind": "synthetic", "approved_ride_ids": ["private-ride-id"]}, "Public climb")
    assert [e["duration_seconds"] for e in result["segments"][0]["efforts"]] == [420, 400]


def test_strava_stream_conversion_and_no_credentials(monkeypatch, tmp_path):
    activity = {"start_date": "2026-01-01T08:00:00Z"}
    streams = {"latlng": {"data": [[47.17, 27.55], [47.171, 27.55]]}, "time": {"data": [0, 10]}}
    p, _ = parse_gpx(streams_to_gpx(activity, streams), "strava")
    assert p[1]["timestamp_utc"] == "2026-01-01T08:00:10Z"
    assert p[0]["elevation"] is None
    streams["time"]["data"] = [0]
    with pytest.raises(ValueError):
        streams_to_gpx(activity, streams)
    monkeypatch.delenv("STRAVA_ACCESS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="STRAVA_ACCESS_TOKEN"):
        sync_strava([123], tmp_path)


def test_strava_mocked_sync_is_deterministic_and_token_errors_are_safe(monkeypatch, tmp_path):
    import ride_replay.strava as strava
    streams = {"latlng": {"data": [[47.17, 27.55], [47.171, 27.55]]}, "time": {"data": [0, 10]}}
    monkeypatch.setattr(strava, "api_get", lambda path, token: streams if "/streams?" in path else {"start_date": "2026-01-01T08:00:00Z", "sport_type": "Ride"})
    sync_strava([123], tmp_path, token="mock-token")
    before = (tmp_path / "strava-123.gpx").read_bytes()
    sync_strava([123], tmp_path, token="mock-token")
    assert (tmp_path / "strava-123.gpx").read_bytes() == before
    with pytest.raises(ValueError, match="unsupported characters") as error:
        sync_strava([123], tmp_path, token="sensitive-token\n")
    assert "sensitive-token" not in str(error.value)


def test_demo_reproducible_and_safe(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    summary = generate_demo(tmp_path / "demo", snapshot)
    before = snapshot.read_bytes()
    generate_demo(tmp_path / "demo", snapshot)
    assert before == snapshot.read_bytes()
    assert summary["accepted"] == 12
    assert summary["rejected"] >= 3
    validate_public_snapshot(json.loads(before))


def test_overlap_rejected():
    with pytest.raises(ValueError, match="overlap"):
        validate_segment({**DEMO_SEGMENT, "finish": DEMO_SEGMENT["start"]})
