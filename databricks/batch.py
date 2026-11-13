"""Parameterized Spark batch job. Requires the ride_replay wheel on the cluster.

Inputs and outputs are private Unity Catalog Volume paths. This source is prepared,
but no Databricks execution is claimed until a successful run is recorded.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ride_replay.matching import detect_efforts, silver_points, validate_segment
from ride_replay.snapshot import build_snapshot, write_json

POINT_SCHEMA = "ride_id string, track_segment long, point_index long, timestamp_utc string, latitude double, longitude double, elevation double"
SILVER_SCHEMA = POINT_SCHEMA + ", quality_flags array<string>, edge_flags array<string>"
EFFORT_SCHEMA = "ride_id string, track_segment long, start_index long, finish_index long, started_at string, elapsed_seconds double, accepted boolean, quality_reasons array<string>"


def run(args):
    import pandas as pd
    from pyspark.sql import SparkSession, functions as F

    spark = SparkSession.builder.appName("ride-replay-batch").getOrCreate()
    segment = validate_segment(json.loads(Path(args.segment_json).read_text(encoding="utf-8")))
    approval = json.loads(Path(args.approval_json).read_text(encoding="utf-8"))
    # Validate publication intent before starting transformations.
    build_snapshot([], approval, segment["label"])
    bronze = spark.read.schema(POINT_SCHEMA).option("multiLine", True).json(args.points_json)
    base = args.output_base.rstrip("/")
    lineage = spark.read.option("multiLine", True).json(args.manifests_dir).select(
        "run_id", "created_at", F.explode("files").alias("file")).select("run_id", "created_at", "file.*")
    lineage.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/import_lineage")
    bronze.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/bronze")

    def records(frame):
        return frame.astype(object).where(pd.notnull(frame), None).to_dict("records")

    def silver_group(frame):
        return pd.DataFrame(silver_points(records(frame), segment), columns=[s.split()[0] for s in SILVER_SCHEMA.split(", ")])

    def gold_group(frame):
        return pd.DataFrame(detect_efforts(records(frame), segment), columns=[s.split()[0] for s in EFFORT_SCHEMA.split(", ")])

    # Each bounded source track segment is processed in source point order by the
    # same pure functions used locally; no interpolation or cross-segment stitching.
    silver = bronze.groupBy("ride_id", "track_segment").applyInPandas(silver_group, schema=SILVER_SCHEMA)
    silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/silver")
    gold = bronze.groupBy("ride_id", "track_segment").applyInPandas(gold_group, schema=EFFORT_SCHEMA)
    gold.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/gold")
    persisted = spark.read.format("delta").load(base + "/gold")
    approved = persisted.filter(F.col("ride_id").isin(approval["approved_ride_ids"]))
    snapshot = build_snapshot([r.asDict(recursive=True) for r in approved.collect()], approval, segment["label"])
    write_json(Path(args.public_output), snapshot)
    # Job ID/run ID are injected by bundle dynamic references. This evidence stays
    # private and is meaningful only when matched to the workspace run page.
    write_json(Path(args.evidence_output), {
        "job_id": args.job_id, "run_id": args.run_id, "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(), "spark_version": spark.version,
        "bronze_points": bronze.count(), "gold_efforts": persisted.count(),
        "snapshot_sha256": hashlib.sha256(Path(args.public_output).read_bytes()).hexdigest(),
        "outputs": [base + "/" + tier for tier in ("import_lineage", "bronze", "silver", "gold")],
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("points-json", "manifests-dir", "segment-json", "approval-json", "output-base", "public-output", "evidence-output", "job-id", "run-id"):
        parser.add_argument("--" + name, required=True)
    run(parser.parse_args())
