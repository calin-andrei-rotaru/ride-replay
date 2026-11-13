# Verification record

Local verification on **13 November 2026**. Synthetic results below do not establish real-ride compatibility or cloud execution.

## Verified locally

- Python 3.14.4: `python -m pytest -q` — **28 passed** after adding local Strava authorization. Coverage includes file identity, GPX segments, directed/repeated passes, quality rejection reasons, XML safety, whitelist publication, deterministic mocked Strava conversion, safe token errors, Windows database-handle release, OAuth callback state/scope checks, token exchange, and real loopback HTTP callback handling with the external Strava exchange mocked.
- A fresh temporary workspace generated **15 synthetic rides / 765 points**. Importing the same files again left both counts at **15 / 765**, with all 15 marked duplicate. Temporary database cleanup succeeded after the handle-lifetime fix.
- The approved synthetic snapshot contains **12 accepted efforts / 3 rejected candidates**. Rejections cover a reverse pass, a 98.4 s sample interval, and a plausible detour that passes both endpoint fences but misses the checkpoint. That detour fails solely for `missing_checkpoint`.
- Source-index check: the first synthetic effort starts at sample 0, reaches the checkpoint at 24, and first enters the finish fence at 49. Source elapsed time is **480.20 s**, publicly rounded to **480 s**. The latest accepted fixture uses the same indices and yields **371.42 s → 371 s**. These checks are reproducible fixture calculations; **zero real efforts have been manually checked**.
- Next.js 16.4.6 / React 19.3.1 / Node 24.14.1: production static build and TypeScript checks passed. Google font files are bundled at build time and self-hosted in the output.
- `npm run check:public` passed against the built `web/out` assets and the exact bundled snapshot. This checks the public field whitelist, known private identifiers/field patterns, and prohibited private file extensions. It is not a blanket guarantee for future additions to the web source.
- Local HTTP responses for `/` and `/snapshot.json` returned **200**. The dashboard reads static JSON and has no Databricks or Strava runtime dependency.
- Terraform **1.14.0**, AWS provider **6.73.0**: `init -backend=false`, `fmt -check`, and `validate` passed. The provider lockfile is tracked. Validation required no AWS credentials or resource changes.
- Databricks Python entrypoint passed Python compilation. Its Spark/Delta execution and bundle deployment are **not tested**.

## Outstanding evidence

- **Real input format:** none available. The user confirmed there are no local GPX exports. No Strava connector was found and no athlete-authorized token was provided. Strava API behavior is based on the official documentation; only mocked streams have been tested.
- **Real segment calibration:** pending at least two real rides through one selected climb. The checked-in segment coordinates and public label are synthetic. Initial 35 m / 30 s thresholds are provisional; they are not measurements from Iași rides.
- **Timing uncertainty:** first in-fence samples are used, without interpolation. With observed samples bracketing each fence crossing, timing uncertainty depends on both endpoint sample intervals; the sum of the intervals is a conservative bound. If the source begins inside a fence or the entry is not bracketed, that physical-crossing bound cannot be established. Inspect source tracks when accepting a real result.
- **Databricks:** no CLI/workspace connection or job run was available. No real run ID, workspace URL, Delta output, or cloud-produced snapshot exists yet. The bundle takes an existing cluster ID and a private volume path; it does not provision compute automatically.
- **Real-data publication:** the live Vercel deployment currently contains only the labeled synthetic fixture. Replacing it with approved real results remains pending real imports, calibration, manual checks, and a Databricks run.
- **Terraform plan/apply:** not run. An account, exact trusted IAM role ARNs, storage names, state backend, and budget must be selected before cloud provisioning. No Databricks provider compatibility is asserted.
- **Browser QA:** blocked by unavailable browser/native UI connections in this session. The browser inventory was empty and the native pipe could not be connected. Responsive breakpoints and keyboard-accessible controls are implemented, but screenshots, visual inspection, and live browser interaction tests have not been performed.
- **GitHub:** at the initial local verification, the empty remote repository had been cloned and implementation files created locally. No commit or push had been made at that point.

## Continuation

The local importer now supports `strava-sync --connect`: an ephemeral loopback OAuth flow, hidden client-secret input, exact read-scope validation, no token persistence, and an optional explicit `--include-private` scope. Tests use the real local HTTP listener and a mocked external token exchange; they do not authorize a real athlete.

The browser/native connection was checked again and remains unavailable. Live athlete authorization, real-data validation, Databricks execution, and cloud Terraform provisioning remain outstanding.

### GitHub and CI

The implementation was committed and pushed to `main` at [`e2d217d`](https://github.com/calin-andrei-rotaru/ride-replay/commit/e2d217d4ddcae02bbd3b1e27c04462c01547679d). [GitHub Actions run 43472239282](https://github.com/calin-andrei-rotaru/ride-replay/actions/runs/43472239282) completed successfully on Ubuntu: all 28 Python tests, deterministic snapshot regeneration, dashboard production build, TypeScript, local public-asset checks, and Terraform initialization/format/validation passed. No private data paths were committed.

### Vercel synthetic demo

The existing authenticated CLI was used to create `smasher421/ride-replay` on the existing Hobby account. The successful deployment is [`dpl_DHNLsmHaaWnjKAzKZLtkwnZHqbsJ`](https://vercel.com/smasher421/ride-replay/DHNLsmHaaWnjKAzKZLtkwnZHqbsJ), with status **Ready** and production URL **https://ride-replay-smoky.vercel.app**. The initial attempt failed because the Output Directory override pointed the Next.js builder at `out`; that override was removed before the successful build.

The project is now connected to GitHub with Root Directory `web`, framework `nextjs`, and Node.js `24.x`. Public production HTTP checks passed: home page 200, `nosniff` response header, exact approved synthetic snapshot, **19 referenced assets** scanned for known private fields/identifiers, and 404 responses for `.env`, `.env.local`, the private database/manifests, and Python source paths. These checks run through `npm run check:deployment -- <URL>`. They verify referenced deployed assets; they are not a browser screenshot or a guarantee about unreferenced future files. No live Databricks service was used to serve the page.

## Real-data completion sequence

See the actionable [real-data runbook](real-data.md). Databricks CLI 1.26.0 has been installed locally from the official release with its archive checksum verified. The serverless/classic bundle configuration passed local shape/type checks against that CLI's schema. Full workspace validation remains pending authentication. [CI run 43477851707](https://github.com/calin-andrei-rotaru/ride-replay/actions/runs/43477851707) passed the actual PySpark/Arrow integration tests against local fixture results. Neither result is a live Databricks or real-rider validation.

The private preparation workflow additionally checks source cadence, ordered climb selection, two accepted source rides, isolated preview serving, and cloud/local parity. Its tests and staging demonstration use explicitly synthetic fixtures. Real-data, manual-review, publication, and Databricks-verification flags remain false until actual evidence is obtained.

1. Authorize your own Strava application for the necessary activity read scope, and import at least two specific GPS rides through the private CLI. Never place tokens in the web project.
2. Inspect manifests and source samples for cadence, timestamp validity, segmentation, and optional altitude. Select and calibrate the directed climb in ignored private configuration.
3. Manually check two accepted passages against their source indices/times and inspect the rejected near-miss example. Record observed endpoint sampling error.
4. Run the parameterized Databricks job in the authorized workspace. Retain its actual run page and evidence JSON; verify the output snapshot hash.
5. Clear rides and the public segment label for publication, explicitly allowlist their private IDs, and validate the resulting public snapshot. Rebuild and inspect static assets.
6. Replace the synthetic demo with the validated real snapshot, redeploy from `web`, and inspect visible content and downloadable assets with Databricks offline.
7. Review and apply a Terraform plan only in the selected authorized account and budget. Record actual plan/apply status, and update this file without converting missing evidence into success claims.
