"""Parameterized Spark batch job. Requires the ride_replay wheel on the cluster.

Inputs and outputs are private Unity Catalog Volume paths. This source is prepared,
but no Databricks execution is claimed until a successful run is recorded.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ride_replay.matching import validate_segment
from ride_replay.snapshot import build_snapshot, write_json
from ride_replay.spark import POINT_SCHEMA, transform_frames
from ride_replay.validation import assert_effort_parity


def run(args):
    from pyspark.sql import SparkSession, functions as F

    spark = SparkSession.builder.appName("ride-replay-batch").getOrCreate()
    segment = validate_segment(json.loads(Path(args.segment_json).read_text(encoding="utf-8")))
    approval = json.loads(Path(args.approval_json).read_text(encoding="utf-8")) if args.approval_json else None
    if approval is not None:
        build_snapshot([], approval, segment["label"])
    bronze = spark.read.schema(POINT_SCHEMA).option("multiLine", True).json(args.points_json)
    base = args.output_base.rstrip("/")
    lineage = spark.read.option("multiLine", True).json(args.manifests_dir).select(
        "run_id", "created_at", F.explode("files").alias("file")).select("run_id", "created_at", "file.*")
    lineage.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/import_lineage")
    bronze.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/bronze")

    # Each bounded source track segment is processed in source point order by the
    # same pure functions used locally; no interpolation or cross-segment stitching.
    silver, gold = transform_frames(bronze, segment)
    silver.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/silver")
    gold.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(base + "/gold")
    persisted = spark.read.format("delta").load(base + "/gold")
    expected_path = Path(args.points_json).parent / "expected-efforts.json"
    parity_checked = expected_path.is_file()
    if parity_checked:
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        assert_effort_parity(expected, [r.asDict(recursive=True) for r in persisted.collect()])
    snapshot_hash = None
    if approval is not None:
        approved = persisted.filter(F.col("ride_id").isin(approval["approved_ride_ids"]))
        snapshot = build_snapshot([r.asDict(recursive=True) for r in approved.collect()], approval, segment["label"])
        write_json(Path(args.public_output), snapshot)
        snapshot_hash = hashlib.sha256(Path(args.public_output).read_bytes()).hexdigest()
    # Job ID/run ID are injected by bundle dynamic references. This evidence stays
    # private and is meaningful only when matched to the workspace run page.
    write_json(Path(args.evidence_output), {
        "job_id": args.job_id, "run_id": args.run_id, "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(), "spark_version": spark.version,
        "bronze_points": bronze.count(), "gold_efforts": persisted.count(),
        "snapshot_sha256": snapshot_hash, "publication_approved": approval is not None,
        "local_cloud_parity_checked": parity_checked,
        "input_bronze_sha256": hashlib.sha256(Path(args.points_json).read_bytes()).hexdigest(),
        "outputs": [base + "/" + tier for tier in ("import_lineage", "bronze", "silver", "gold")],
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval-json", default="")
    for name in ("points-json", "manifests-dir", "segment-json", "output-base", "public-output", "evidence-output", "job-id", "run-id"):
        parser.add_argument("--" + name, required=True)
    run(parser.parse_args())
