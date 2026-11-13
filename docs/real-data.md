# Validate real rides end to end

[Project overview](../README.md) · [Full guide](guide.md) · [Verification record](verification.md)

This workflow keeps real GPS tracks private while checking the importer, climb matcher, dashboard, and Databricks output against the same inputs. A prepared package or a passing fixture test is not proof that real rides or a live job have been validated.

## 1. Connect an account that has real rides

Use your own [Strava account](https://www.strava.com/) and register a [Strava API application](https://www.strava.com/settings/api). A newly created empty account does not provide ride data: record or import at least two genuine GPS cycling activities that share a climb. Do not upload synthetic fixtures to Strava as real activities.

Activate the local Python environment, then list your recent cycling activities:

```text
ride-replay strava-list --connect --limit 20
```

The command prompts for the API app's client ID and hidden client secret, then opens Strava authorization. The resulting list is private terminal output and includes activity URLs and whether a visible GPS start was returned. That GPS indicator is only a preliminary hint; stream import performs the actual compatibility check. Indoor/manual rides may have no usable GPS.

Add `--include-private` if Only You activities or privacy-zone data are needed. No write scope is requested. Secrets and access tokens are not saved. Each `--connect` session authorizes independently; supplied authorized tokens remain supported through `--prompt-token` or the local environment.

Choose two specific real activities through the same climb:

```text
ride-replay strava-sync --connect --activity-id FIRST_ID --activity-id SECOND_ID
ride-replay import data/strava
ride-replay inspect
```

Replace `FIRST_ID` and `SECOND_ID` with numeric activity IDs. Inspect source segment counts, missing time, elevation availability, timestamp range, and median/p95/maximum sample intervals. Import the same files again and confirm the ride and point counts remain stable. Import records are exact-file identities; two differently exported copies of one physical ride do not establish two separate efforts.

## 2. Select and calibrate the real climb

Choose start, intermediate checkpoint, and finish points from one source track segment. Use the private point table to identify the indices, then create private configuration:

```text
ride-replay select-segment --ride-id RIDE_ID --track-segment 0 --indices START CHECKPOINT FINISH --label "My selected climb"
ride-replay compare --segment data/segment.json
```

Replace the index placeholders with increasing integer point indices. Review the resulting private `data/segment.json` and tune its geofence radius and gap/jump thresholds against the real tracks. Initial defaults remain provisional. Check that both source routes pass through the intended checkpoint in the intended direction, without segment stitching.

## 3. Prepare a private validation package

```text
ride-replay prepare-run --segment data/segment.json --ride-id FIRST_RIDE_ID --ride-id SECOND_RIDE_ID --data-kind real --output data/real-run-001
```

Both selected rides must contain an accepted passage. The command refuses unknown rides, a mismatched climb, or reuse of a nonempty run directory. It writes:

- `input/bronze.json`, `input/segment.json`, and selected hash-based import lineage.
- `input/expected-efforts.json`, with local accepted/rejected results for exact cloud comparison.
- `validation.json`, with input hashes, sample summaries, declared data kind, and explicitly unverified status.
- `manual-checks.json`, with source crossing indices and timing for review. Every review starts unchecked.
- `preview/snapshot.json`, containing only anonymous durations and counts for a private dashboard preview.

`--data-kind real` records your declaration; it does not prove provenance or mark the data verified. The command does not create a publication approval file and does not change `web/public/snapshot.json`.

Build the dashboard once with `cd web; npm run build`, return to the repository root, and view the selected data locally:

```text
ride-replay preview --snapshot data/real-run-001/preview/snapshot.json
```

Open **http://127.0.0.1:8765**. This server binds only to loopback, serves the built dashboard and selected anonymous snapshot, and leaves the public demo unchanged. Stop it with Ctrl+C.

Manually check at least two accepted efforts against their original tracks. Confirm direction, checkpoint passage, source segment, endpoint samples, and elapsed-time subtraction. Record notes in `manual-checks.json` only after reviewing the source, including observed endpoint sampling uncertainty. A computed candidate is not a manual review.

## 4. Authenticate to the intended Databricks workspace

Use your existing authorized workspace, or create your own [Databricks Free Edition workspace](https://www.databricks.com/learn/free). Account sign-in, account terms, and any requested identity steps must be completed by the account owner. Free Edition uses serverless resources and fair-use quotas; paid workspaces need an agreed compute budget before a run.

The local CLI is available at `tools/databricks/databricks.exe` in this checkout; it is ignored by Git. The examples below assume `databricks` is on PATH. In PowerShell you can use `.\tools\databricks\databricks.exe` instead.

```text
databricks auth login --profile ride-replay
databricks current-user me --profile ride-replay
```

Select the intended workspace in the browser. Keep the CLI's credentials outside the repository. Confirm a private Unity Catalog Volume with appropriate access; do not use a shared public location for GPS inputs.

## 5. Stage and run on authorized compute

After confirming the destination workspace, private volume, and budget/quota, upload only the prepared input directory:

```text
databricks fs cp data/real-run-001/input dbfs:/Volumes/CATALOG/SCHEMA/VOLUME/input --recursive --profile ride-replay
```

Replace the volume placeholders. An existing `input/` can be reused only after you review which dataset it contains; use a separate volume/run location when retaining prior input evidence is required. Raw points are private and must never go into the Vercel project.

For serverless, including compatible Free Edition workspaces:

```text
databricks bundle validate -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
databricks bundle deploy -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
databricks bundle run compare_climb -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
```

For an authorized existing classic cluster, use `-t classic` with an explicit `cluster_id` variable. The bundle has no schedule, one concurrent run, timeouts, and retries disabled. Timeouts do not constitute a spending cap.

With no `approval_path`, the job writes private Delta results and run evidence, and produces no public snapshot. If `expected-efforts.json` is staged, every accepted/rejected effort, source index, quality reason, and elapsed time must agree with local execution before success evidence is written. The allowed floating-point difference is one microsecond.

Retrieve the actual `evidence/<run-id>.json` and check:

- The run page shows success in the intended workspace.
- `local_cloud_parity_checked` is true.
- `input_bronze_sha256` matches the private `validation.json` input hash.
- The observed row counts and Gold efforts match the source review.

Keep this evidence private: it includes workspace run identifiers and storage paths. A passing Spark CI job establishes engine compatibility for fixtures; it does not substitute for this live run or real-ride checks.

## 6. Publish only after clearance

Private processing and local preview do not clear a ride for public publication. After explicit clearance, create an allowlist, generate the anonymous snapshot, validate it and the built/deployed assets, and retain the actual Databricks run evidence used for the export. The [full guide](guide.md#publish-only-approved-efforts) covers those commands.

Until then, the public site continues to use its labeled synthetic snapshot. Do not mark any real-data milestone complete without the corresponding source review and actual run evidence.
