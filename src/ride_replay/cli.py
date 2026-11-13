import argparse
import getpass
import json
import sys
from pathlib import Path

from .fixtures import generate_demo
from .ingest import import_directory, load_points
from .matching import detect_efforts, silver_points, validate_segment
from .snapshot import build_snapshot, validate_public_snapshot, write_json
from .strava import sync_strava
from .strava_auth import authorize_strava


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Ride Replay: private imports, directed climbs, safe snapshots")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import", help="Import one directory of GPX files, non-recursively")
    ingest.add_argument("directory", type=Path)
    ingest.add_argument("--database", type=Path, default=Path("data/rides.sqlite"))
    ingest.add_argument("--manifests", type=Path, default=Path("data/manifests"))
    compare = commands.add_parser("compare")
    compare.add_argument("--database", type=Path, default=Path("data/rides.sqlite"))
    compare.add_argument("--segment", type=Path, required=True)
    compare.add_argument("--output", type=Path, default=Path("data/efforts.json"))
    compare.add_argument("--bronze-output", type=Path, default=Path("data/bronze.json"))
    compare.add_argument("--silver-output", type=Path, default=Path("data/silver.json"))
    export = commands.add_parser("export")
    export.add_argument("--efforts", type=Path, default=Path("data/efforts.json"))
    export.add_argument("--approval", type=Path, required=True)
    export.add_argument("--segment", type=Path, required=True)
    export.add_argument("--output", type=Path, default=Path("web/public/snapshot.json"))
    demo = commands.add_parser("demo")
    demo.add_argument("--workspace", type=Path, default=Path("data/demo"))
    demo.add_argument("--output", type=Path, default=Path("web/public/snapshot.json"))
    strava = commands.add_parser("strava-sync", help="Read specific authorized Strava activity GPS streams")
    strava.add_argument("--activity-id", action="append", type=int, required=True)
    strava.add_argument("--output", type=Path, default=Path("data/strava"))
    auth = strava.add_mutually_exclusive_group()
    auth.add_argument("--prompt-token", action="store_true", help="Read the token with hidden input instead of an environment variable")
    auth.add_argument("--connect", action="store_true", help="Authorize your Strava API app in the browser for this import session")
    strava.add_argument("--include-private", action="store_true", help="With --connect, request activity:read_all for Only You rides and privacy-zone data")
    verify = commands.add_parser("verify-snapshot")
    verify.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "import":
            result = import_directory(args.directory, args.database, args.manifests)
        elif args.command == "compare":
            segment = validate_segment(read_json(args.segment))
            points = load_points(args.database)
            efforts = detect_efforts(points, segment)
            write_json(args.bronze_output, points)
            write_json(args.silver_output, silver_points(points, segment))
            write_json(args.output, efforts)
            result = {"accepted": sum(e["accepted"] for e in efforts), "rejected": sum(not e["accepted"] for e in efforts), "output": str(args.output)}
        elif args.command == "export":
            snapshot = build_snapshot(read_json(args.efforts), read_json(args.approval), read_json(args.segment)["label"])
            write_json(args.output, snapshot)
            result = {"output": str(args.output), "data_kind": snapshot["data_kind"]}
        elif args.command == "demo":
            result = generate_demo(args.workspace, args.output)
        elif args.command == "strava-sync":
            if args.include_private and not args.connect:
                raise ValueError("--include-private requires --connect; supplied tokens use their existing granted scopes")
            if any(activity_id <= 0 for activity_id in args.activity_id):
                raise ValueError("Activity IDs must be positive integers")
            token = authorize_strava(include_private=args.include_private) if args.connect else (
                getpass.getpass("Strava activity read access token (hidden): ") if args.prompt_token else None)
            result = sync_strava(args.activity_id, args.output, token=token)
        else:
            validate_public_snapshot(read_json(args.file))
            result = {"valid": True}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "import" and any(f["status"] == "rejected" for f in result["files"]):
            return 1
        return 0
    except (ValueError, KeyError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
