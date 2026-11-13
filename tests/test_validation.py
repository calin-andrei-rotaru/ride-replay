import json
from pathlib import Path

import pytest

from ride_replay.fixtures import DEMO_SEGMENT, make_gpx
from ride_replay.ingest import import_directory, load_points
from ride_replay.matching import detect_efforts
from ride_replay.validation import assert_effort_parity, inspect_rides, prepare_run, segment_from_indices


def dataset(tmp_path):
    rides = tmp_path / "rides"
    rides.mkdir()
    for day in (1, 2):
        (rides / f"ride-{day}.gpx").write_bytes(make_gpx(day=day))
    database = tmp_path / "rides.sqlite"
    manifest = import_directory(rides, database, tmp_path / "manifests")
    segment = tmp_path / "segment.json"
    segment.write_text(json.dumps(DEMO_SEGMENT), encoding="utf-8")
    return database, segment, [r["ride_id"] for r in manifest["files"]]


def test_private_inspection_and_source_index_selection(tmp_path):
    db, _, ids = dataset(tmp_path)
    summary = inspect_rides(db)
    assert len(summary) == 2
    assert all(r["sampling_seconds_median"] == pytest.approx(8.4) for r in summary)
    assert all(r["point_count"] == 51 and r["missing_timestamps"] == 0 for r in summary)
    selected = segment_from_indices(db, ids[0], 0, [0, 25, 50], "Private climb")
    assert selected["start"] == DEMO_SEGMENT["start"] and selected["finish"] == DEMO_SEGMENT["finish"]
    with pytest.raises(ValueError, match="ordered"):
        segment_from_indices(db, ids[0], 0, [50, 25, 0], "Private climb")
    with pytest.raises(ValueError, match="must exist"):
        segment_from_indices(db, ids[0], 1, [0, 25, 50], "Private climb")


def test_prepare_run_requires_two_accepted_rides_and_does_not_approve(tmp_path):
    db, segment, ids = dataset(tmp_path)
    output = tmp_path / "private-run"
    result = prepare_run(db, segment, ids, output, "synthetic")
    assert result["rides"] == 2 and result["accepted"] == 2
    report = json.loads((output / "validation.json").read_text())
    assert report["declared_data_kind"] == "synthetic"
    assert not report["publication_approved"] and not report["real_data_verified"] and not report["databricks_run_verified"]
    assert not (output / "input/approval.json").exists()
    assert (output / "preview/snapshot.json").is_file()
    expected = json.loads((output / "input/expected-efforts.json").read_text())
    assert_effort_parity(expected, detect_efforts(load_points(db), DEMO_SEGMENT))
    assert all(not r["reviewed_against_source"] for r in json.loads((output / "manual-checks.json").read_text()))
    with pytest.raises(ValueError, match="empty run directory"):
        prepare_run(db, segment, ids, output, "synthetic")
    with pytest.raises(ValueError, match="two distinct"):
        prepare_run(db, segment, ids[:1], tmp_path / "single", "synthetic")
    with pytest.raises(ValueError, match="must exist"):
        prepare_run(db, segment, [ids[0], "unknown"], tmp_path / "unknown", "synthetic")


def test_prepare_run_rejects_wrong_climb_before_writing(tmp_path):
    db, segment, ids = dataset(tmp_path)
    config = dict(DEMO_SEGMENT)
    for name in ("start", "checkpoint", "finish"):
        config[name] = [config[name][0] - 1, config[name][1]]
    segment.write_text(json.dumps(config), encoding="utf-8")
    output = tmp_path / "failed"
    with pytest.raises(ValueError, match="accepted passage"):
        prepare_run(db, segment, ids, output, "synthetic")
    assert not output.exists()


def test_parity_detects_cloud_count_quality_and_timing_changes(tmp_path):
    db, _, _ = dataset(tmp_path)
    expected = detect_efforts(load_points(db), DEMO_SEGMENT)
    with pytest.raises(ValueError, match="counts"):
        assert_effort_parity(expected, expected[:1])
    for changed in ({"accepted": False}, {"quality_reasons": ["sampling_gap"]}, {"elapsed_seconds": 999}):
        actual = [{**expected[0], **changed}, expected[1]]
        with pytest.raises(ValueError, match="Cloud/local"):
            assert_effort_parity(expected, actual)


def test_strava_list_filters_and_pages_only_the_authenticated_athlete(monkeypatch):
    from ride_replay import strava
    requested = []
    first = [{"id": n, "sport_type": "Run"} for n in range(100)]
    second = [{"id": 101, "sport_type": "Ride", "name": "Real ride name", "start_latlng": [47, 27]},
        {"id": 102, "sport_type": "VirtualRide", "name": "Indoor", "start_latlng": []}]
    def get(path, token):
        requested.append(path)
        return first if path.endswith("&page=1") else second
    monkeypatch.setattr(strava, "api_get", get)
    rides = strava.list_rides(2, token="mock-token")
    assert [r["activity_id"] for r in rides] == [101, 102]
    assert rides[0]["has_visible_gps"] and not rides[1]["has_visible_gps"]
    assert requested == ["/athlete/activities?per_page=100&page=1", "/athlete/activities?per_page=100&page=2"]
    with pytest.raises(ValueError, match="between"):
        strava.list_rides(51, token="mock-token")


def test_private_preview_serves_only_the_static_app_and_selected_snapshot(tmp_path):
    import threading
    from urllib.error import HTTPError
    from urllib.request import urlopen
    from ride_replay.preview import preview_server
    from ride_replay.snapshot import build_snapshot
    db, _, ids = dataset(tmp_path)
    snapshot = build_snapshot(detect_efforts(load_points(db), DEMO_SEGMENT),
        {"data_kind": "synthetic", "approved_ride_ids": ids}, "Private preview")
    file = tmp_path / "selected.json"
    file.write_text(json.dumps(snapshot), encoding="utf-8")
    web = tmp_path / "static"
    web.mkdir()
    (web / "index.html").write_text("<h1>Ride Replay</h1>", encoding="utf-8")
    (web / "snapshot.json").write_text('{}', encoding="utf-8")
    server = preview_server(file, web, 0)
    assert server.server_address[0] == "127.0.0.1"
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/snapshot.json", timeout=5) as response:
            assert json.load(response) == snapshot
            assert response.headers["Cache-Control"] == "no-store"
        with pytest.raises(HTTPError) as error:
            urlopen(base + "/../rides.sqlite", timeout=5)
        assert error.value.code == 404
        assert (web / "snapshot.json").read_text() == '{}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
