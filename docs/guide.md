# Ride Replay usage guide

[Back to the project overview](../README.md)

A private cycling activity importer and a Next.js dashboard for one question: **am I getting quicker on the same climb?**

**Live demo: [ride-replay-smoky.vercel.app](https://ride-replay-smoky.vercel.app)**

The demo uses **synthetic rides**, explicitly labeled throughout. It is not connected to a Strava account and contains no real rider data. The source repository is public; keep tracks, tokens, segment coordinates, and import manifests in ignored `data/` or outside this checkout.

## Run locally

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
ride-replay demo
python -m pytest -q
Set-Location web
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. If PowerShell blocks activation, use `.\.venv\Scripts\python -m ride_replay.cli` in place of `ride-replay`, and `.\.venv\Scripts\python -m pytest -q` for tests. On macOS/Linux activate with `source .venv/bin/activate`.

The bundled snapshot lets the dashboard start without running Python. It contains 12 accepted synthetic efforts from 15 approved synthetic rides; the other 3 candidates demonstrate a reverse pass, a sampling gap, and a plausible alternate route that misses the checkpoint. The chart uses anonymous chronological effort order, not calendar dates. Click a chart sample or table row to select an effort; filter to the latest 6, sort history, paginate, or export the current effort selection as CSV.

## Use your own rides

### Strava

The private importer reads activity GPS/time/altitude streams using [Strava's documented API](https://developers.strava.com/docs/reference/#api-Streams-getActivityStreams). It does not scrape accounts or read other athletes' private activities.

1. Register your own [Strava API application](https://www.strava.com/settings/api). You will need its client ID and client secret. The local flow uses a loopback callback, which [Strava explicitly permits](https://developers.strava.com/docs/authentication/).
2. Choose two cycling activity IDs from your Strava activity URLs, then run:

```powershell
ride-replay strava-sync --connect --activity-id 123456789 --activity-id 987654321
ride-replay import data/strava
```

3. Enter the client ID and secret at the local prompts (the secret input is hidden), then authorize the app in the browser. The CLI checks the one-time callback state and granted scope before exchanging the authorization code. A temporary server listens only on `127.0.0.1` and closes after success, denial, or timeout. The token and secret remain in process memory and are not saved. Close the import session when finished. `.env` files are not loaded automatically; `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` can optionally be set in your local shell instead of using prompts.

The default scope is `activity:read` for Everyone/Followers activities. Add **`--include-private`** to `--connect` for `activity:read_all`, which includes Only You activities and privacy-zone data. No write scope is requested. Granting access is separate from clearing rides for publication: the explicit export allowlist still applies.

If you already have an authorized access token, use `--prompt-token` instead of `--connect`, or set `STRAVA_ACCESS_TOKEN` locally. Never paste credentials into chat, commit them, or add them to Vercel. A token copied from the API app settings may lack the required activity scopes.

Replace the example IDs with your own. GPS and elapsed time streams must align; manual and indoor rides without GPS are rejected. Optional altitude is preserved. Gaps in elapsed time remain gaps and are quality-checked. Repeating the same activity stream produces the same GPX bytes and import identity. Different exports of the same physical ride are intentionally not deduplicated by content similarity.

Strava access tokens expire. This version uses a token for one import session and reports authentication/scope/rate-limit failures without printing credentials. Run `--connect` again when needed; no refresh token is retained. Live Strava behavior remains unverified until you supply API app credentials and authorize real activities.

### GPX and the import contract

```powershell
ride-replay import 'C:\path\to\rides'
```

The importer scans the immediate directory for `.gpx`/`.GPX` files. It stores content-addressed records and points in `data/rides.sqlite` and writes a unique JSON run manifest into `data/manifests/` on every invocation.

- SHA-256 of the exact file bytes is the import identity. Renaming or reimporting identical bytes never adds rides or points; each run still records the duplicate result. Rejected files also have stable import records.
- GPX 1.1 namespace, other GPX root namespaces, and unnamespaced tracks are supported through namespace-aware direct-child parsing. Tracks are not joined. Each `trkseg` receives a globally increasing segment number within the file; point indices restart at zero within each segment. Routes and waypoints are not treated as timestamped activity tracks.
- The point schema is `ride_id`, `track_segment`, `point_index`, `timestamp_utc`, `latitude`, `longitude`, and nullable `elevation`. UTC timestamps are stored as ISO 8601 strings. Timezone offsets are normalized; naive, absent, or invalid timestamps become null and are flagged. No timestamps are invented. Untimed rides can import but cannot yield accepted efforts.
- Coordinate numbers must be finite. Out-of-range coordinates are retained in Bronze and flagged in Silver. Elevation is optional, finite when present. Malformed numeric fields reject the file atomically.
- DTDs, XML entities, and external references are disabled with `defusedxml`. Maximum size is 25 MiB and maximum count is 250,000 track points per file. Oversized/malformed/empty-track files are recorded as rejected, without partial point writes.
- Parse details record segment count, usable timestamps, elevation availability, and minimum/maximum observed sample interval. Source point order is preserved, including out-of-order timestamps so Silver can detect them.

The manifest includes private filenames and import lineage. **Do not copy it into `web/public`.** No real sample has established field compatibility yet.

### Select a climb and compare

```powershell
Copy-Item config/segment.example.json data/segment.json
# Edit data/segment.json using coordinates from your own track.
ride-replay compare --segment data/segment.json
```

The checked-in coordinates are **fictional fixture geometry**, not a verified climb in Iași. Replace start, checkpoint, and finish with your chosen directed climb. Choose a checkpoint that distinguishes the intended route from alternatives, and a public label you have cleared for sharing.

`compare` writes private `data/bronze.json`, `data/silver.json`, and `data/efforts.json`. Bronze uses the import point schema; SQLite and the run manifests preserve lineage. Silver adds per-point `quality_flags` and incoming `edge_flags` for invalid coordinates, missing or non-increasing time, long sampling gaps, and implausible GPS jumps.

Gold scans source order within each continuous track segment, recognizes entries into non-overlapping start → checkpoint → finish geofences, and supports repeated passages. Reverse, incomplete, restarted, checkpoint-missing, sparse, bad-time, gap, jump, and excessively long candidates retain explicit rejection reasons. It does not stitch across GPX segments or sort points by time to hide recording errors.

Initial **provisional** defaults are 35 m radius, 30 s maximum intersample gap, 25 m/s jump threshold, at least 5 samples, and 3,600 s maximum effort duration. They suit the synthetic fixture's roughly 7.6–9.8 s sampling and are **not calibrated against a real ride**. Inspect your first real imports and tune them before relying on comparisons. Start/checkpoint/finish geofences must not overlap.

Time uses the first valid recorded sample inside each endpoint geofence, with no interpolation. For crossings bracketed by recorded samples, a fence entry is later than the physical boundary crossing by up to the local sample interval; the difference of the two delays affects elapsed time. A conservative absolute uncertainty bound is the sum of the two observed endpoint intervals. If both are within the provisional gap threshold, that bound is at most 60 s. If a track begins inside a fence or an entry is not bracketed, the physical-crossing uncertainty cannot be bounded from those samples alone. Differences smaller than the observed sampling uncertainty should not be treated as proven improvement. Elapsed time includes stops. Rounding to whole seconds adds up to another half-second.

The synthetic source was manually checked at the start sample (index 0), checkpoint (index 24), and first finish sample (index 49): the first effort's time is `490 × 49/50 = 480.20 s → 480 s`, and the latest is `379 × 49/50 = 371.42 s → 371 s`. These are fixture checks, not the required two real-ride checks. See [verification status](verification.md).

### Publish only approved efforts

```powershell
Copy-Item config/approval.example.json data/approval.json
# Explicitly add cleared ride_id values from the local manifest.
ride-replay export --segment data/segment.json --approval data/approval.json
ride-replay verify-snapshot web/public/snapshot.json
```

An empty allowlist is rejected. Only candidates from allowlisted rides contribute to the public efforts or aggregate counts. The exporter constructs a new object with these fields only:

```json
{
  "schema_version": 1,
  "data_kind": "synthetic",
  "segments": [{
    "label": "Approved public label",
    "efforts": [{"order": 1, "duration_seconds": 480}],
    "counts": {"rides": 1, "accepted": 1, "rejected": 0}
  }]
}
```

Metadata records the schema and whether data is synthetic or real. No GPS, exact date, original filename, private ID, or detailed rejection reason is exported. Anonymous order remains chronological; equal start times are deterministically ordered internally. Counts describe detected candidates, not all unrecognized activity points. Approve the label itself as well as the rides. A segment selector appears in the UI and supports additional approved segments in the same schema; the v1 CLI publishes one climb.

## Build and deployment

```powershell
Set-Location web
npm run build
npm run typecheck
npm run check:public
```

The [Next.js static export](https://nextjs.org/docs/app/guides/static-exports) is written to `web/out`. It needs no Python, Strava token, database, or live Databricks connection to serve. `check:public` validates the snapshot field allowlist, confirms the built snapshot matches, and checks built files for known private fields, IDs, and file types. Review any future public assets before publishing.

The synthetic demo is deployed to Vercel in the `smasher421/ride-replay` project, linked to this GitHub repository with **Root Directory `web`**, the Next.js framework preset, and Node.js 24.x. Future Git pushes trigger deployment. `web/vercel.json` sets the build, asset checks, and response headers. Leave Vercel's Output Directory override unset: its Next.js builder needs the framework manifests in `.next` and handles the static export automatically. Forcing that setting to `out` causes `NEXT_NO_ROUTES_MANIFEST` even when the app builds successfully.

Do not add Strava or raw-storage credentials. Rebuild/redeploy after replacing the approved snapshot. Check the actual deployed page, exact snapshot, referenced frontend assets, and private-path 404 responses with:

```powershell
npm run check:deployment -- https://ride-replay-smoky.vercel.app
```

The live demo has passed these HTTP/asset checks without any live Databricks connection. Browser interaction/visual QA is still outstanding; there are no claims of real-ride validation or a Databricks job run.

## Databricks batch path

`databricks/batch.py` uses the same matching functions locally and through grouped PySpark/Arrow transformations. It writes private import lineage and Bronze/Silver/Gold Delta outputs. A real Databricks run still requires your workspace authentication, a private Unity Catalog Volume, and an authorized compute budget.

The default **serverless** target supports serverless workspaces, including compatible Free Edition workspaces. It uses environment version 4 (Python 3.12) and installs the built project wheel. The **classic** target accepts an existing cluster; it does not provision a cluster. Both targets have one concurrent run, explicit timeouts, no schedule, and automatic retries disabled. Timeouts limit duration, not the monetary cost of a paid workspace.

Install the [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install), activate the local Python environment, and install `.[dev]` so the wheel builder is available. This checkout also has a locally installed CLI at `tools/databricks/databricks.exe` (ignored by Git). Authenticate using browser OAuth:

```text
databricks auth login --profile ride-replay
```

Choose your workspace in the browser. Keep credentials in the CLI's user profile, outside Git. Upload private `bronze.json`, `segment.json`, and import manifests beneath a private `/Volumes/CATALOG/SCHEMA/VOLUME/input/` path. The bundle explicitly excludes local ride data, virtual environments, and web secrets from source synchronization.

For serverless:

```text
databricks bundle validate -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
databricks bundle deploy -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
databricks bundle run compare_climb -t serverless -p ride-replay --var 'volume_path=/Volumes/CATALOG/SCHEMA/VOLUME'
```

For classic compute, select `-t classic` and additionally supply `--var 'cluster_id=YOUR_EXISTING_CLUSTER'`. Deployment does not run the job; the final command does and may consume compute quota or incur costs.

Publication approval is optional for a private validation run. With no `approval_path`, the job writes private Delta results and evidence, and generates no public snapshot. After rides are explicitly cleared, upload the approval JSON and add `--var 'approval_path=/Volumes/CATALOG/SCHEMA/VOLUME/input/approval.json'`. Only then is a sanitized snapshot written under `public-ready/`.

The job writes `evidence/<run-id>.json` after successful outputs, with run/job IDs, counts, Spark version, Delta paths, publication status, and the snapshot hash when a snapshot was generated. Match that record against the actual workspace run page. A local schema check or Spark CI test is not evidence that a Databricks job ran. Copy a validated snapshot into the web project only after explicit publication approval.

## Terraform publishing path

`infra/` defines private, encrypted, versioned S3 storage; public-access blocks; TLS-only bucket policies; a role allowed to write exactly `public-ready/snapshot.json`; and a separate role allowed to read that object. Trust policies name existing approved IAM role ARNs. Neither role receives raw bucket access. Optional raw storage uses a separate bucket and defaults off. No access keys are generated, and the static Vercel app needs no storage credentials.

```text
terraform -chdir=infra fmt -check
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

For an eventual authorized account, copy `example.tfvars` to ignored `terraform.tfvars`, replace all placeholders, choose a secure remote state backend, agree the budget, and review a saved plan before apply. No cloud plan or apply is claimed. The reproducible Databricks bundle remains separate because no workspace/provider compatibility has been established.

## Tests and current limits

Python tests cover exact-file repeat imports, source segmentation, forward/reverse/repeated passes, gaps, plausible checkpoint near misses, GPS jumps, invalid coordinates/times, sparse data, XML attacks and size limits, allowlist privacy, deterministic demo generation, and Strava stream alignment. CI checks the Python pipeline, deterministic bundled snapshot, Next.js build/types/assets, and Terraform format/schema validation.

No real GPX or authorized Strava sample is available yet. Real compatibility, two manually verified real efforts, Databricks execution, browser visual/interaction QA, and cloud Terraform plan/apply remain outstanding. The synthetic Vercel demo and its referenced public assets have been checked over HTTP. The complete status and observed evidence are in [docs/verification.md](verification.md).
