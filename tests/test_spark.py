"""Exercise the actual PySpark/Arrow boundary; optional outside the Spark CI job."""
import pytest

pytest.importorskip("pyspark")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from pyspark.sql import SparkSession
from ride_replay.fixtures import DEMO_SEGMENT, make_gpx
from ride_replay.ingest import parse_gpx
from ride_replay.matching import detect_efforts, silver_points
from ride_replay.spark import POINT_SCHEMA, transform_frames


@pytest.fixture(scope="module")
def spark():
    session = (SparkSession.builder.master("local[2]").appName("ride-replay-integration")
        .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2").getOrCreate())
    yield session
    session.stop()


def canonical(rows):
    return sorted(rows, key=lambda p: (p["ride_id"], p["track_segment"], p.get("point_index", p.get("start_index", 0))))


def test_spark_matches_local_for_accepted_and_rejected_tracks(spark):
    points = []
    for index, options in enumerate(({}, {"reverse": True}, {"gap": True}, {"near_miss": True}, {"split": True}, {"timestamps": False})):
        points.extend(parse_gpx(make_gpx(**options), f"fixture-{index}")[0])
    silver, gold = transform_frames(spark.createDataFrame(points, POINT_SCHEMA), DEMO_SEGMENT)
    assert canonical([r.asDict(recursive=True) for r in silver.collect()]) == canonical(silver_points(points, DEMO_SEGMENT))
    assert canonical([r.asDict(recursive=True) for r in gold.collect()]) == canonical(detect_efforts(points, DEMO_SEGMENT))


def test_spark_handles_nullable_elevation_and_an_unmatched_ride(spark):
    points = parse_gpx(make_gpx(), "unmatched")[0]
    for point in points:
        point["elevation"] = None
        point["latitude"] -= 1
    silver, gold = transform_frames(spark.createDataFrame(points, POINT_SCHEMA), DEMO_SEGMENT)
    assert silver.count() == len(points)
    assert gold.count() == 0
