"""Spark transformations shared by the Databricks job and integration checks."""
from .matching import detect_efforts, silver_points, validate_segment

POINT_SCHEMA = "ride_id string, track_segment long, point_index long, timestamp_utc string, latitude double, longitude double, elevation double"
SILVER_SCHEMA = POINT_SCHEMA + ", quality_flags array<string>, edge_flags array<string>"
EFFORT_SCHEMA = "ride_id string, track_segment long, start_index long, finish_index long, started_at string, elapsed_seconds double, accepted boolean, quality_reasons array<string>"


def transform_frames(bronze, segment):
    import pandas as pd

    segment = validate_segment(dict(segment))

    def records(frame):
        return frame.astype(object).where(pd.notnull(frame), None).to_dict("records")

    def silver_group(frame):
        return pd.DataFrame(silver_points(records(frame), segment), columns=[s.split()[0] for s in SILVER_SCHEMA.split(", ")])

    def gold_group(frame):
        return pd.DataFrame(detect_efforts(records(frame), segment), columns=[s.split()[0] for s in EFFORT_SCHEMA.split(", ")])

    grouped = bronze.groupBy("ride_id", "track_segment")
    return (grouped.applyInPandas(silver_group, schema=SILVER_SCHEMA),
        grouped.applyInPandas(gold_group, schema=EFFORT_SCHEMA))
