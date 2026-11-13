"""Read an authorized athlete's GPS streams into private GPX files."""
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree.ElementTree import Element, SubElement, tostring

from .ingest import MAX_BYTES, MAX_POINTS, parse_gpx, utc_time

API = "https://www.strava.com/api/v3"
CYCLING_TYPES = {"Ride", "MountainBikeRide", "GravelRide", "EBikeRide", "EMountainBikeRide", "VirtualRide"}


def access_token(token=None):
    token = token or os.environ.get("STRAVA_ACCESS_TOKEN")
    if not token:
        raise ValueError("Set STRAVA_ACCESS_TOKEN locally to an authorized activity:read or activity:read_all token. Never paste tokens into chat.")
    if not re.fullmatch(r"[A-Za-z0-9._~-]+", token):
        raise ValueError("Strava token contains unsupported characters; enter the token without whitespace")
    return token


def list_rides(limit=20, token=None):
    if not 1 <= limit <= 50:
        raise ValueError("Choose a ride limit between 1 and 50")
    token = access_token(token)
    rides = []
    for page in range(1, 6):
        activities = api_get(f"/athlete/activities?per_page=100&page={page}", token)
        if not isinstance(activities, list):
            raise ValueError("Strava returned an invalid activity list")
        for activity in activities:
            sport = activity.get("sport_type", activity.get("type"))
            if sport in CYCLING_TYPES:
                rides.append({"activity_id": activity["id"], "name": activity.get("name", ""),
                    "start_date": activity.get("start_date"), "sport_type": sport,
                    "distance_m": activity.get("distance"), "elapsed_seconds": activity.get("elapsed_time"),
                    "has_visible_gps": bool(activity.get("start_latlng")),
                    "url": f'https://www.strava.com/activities/{activity["id"]}'})
                if len(rides) == limit:
                    return rides
        if len(activities) < 100:
            break
    return rides


def api_get(path, token):
    request = Request(API + path, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Strava response exceeds size limit")
        return json.loads(data)
    except HTTPError as error:
        guidance = {401: "Token expired or invalid; authorize again.", 403: "Check granted activity read scopes.", 404: "Activity unavailable to this token.", 429: "Rate limit reached; retry later."}
        raise ValueError(f"Strava HTTP {error.code}. {guidance.get(error.code, 'Try again later.')}" ) from None


def streams_to_gpx(activity, streams):
    coords = streams.get("latlng", {}).get("data", [])
    times = streams.get("time", {}).get("data", [])
    altitude = streams.get("altitude", {}).get("data")
    if not coords or len(coords) != len(times) or len(coords) > MAX_POINTS:
        raise ValueError("Activity needs aligned GPS and time streams; indoor/manual rides are unsupported")
    if altitude is not None and len(altitude) != len(coords):
        raise ValueError("Altitude stream is not aligned")
    start_text = utc_time(activity.get("start_date"))
    if not start_text:
        raise ValueError("Strava activity has no usable UTC start_date")
    start = datetime.fromisoformat(start_text)
    root = Element("gpx", {"version": "1.1", "creator": "Ride Replay Strava import", "xmlns": "http://www.topografix.com/GPX/1/1"})
    segment = SubElement(SubElement(root, "trk"), "trkseg")
    previous = -1
    for index, (coord, offset) in enumerate(zip(coords, times)):
        if not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset < 0 or offset <= previous:
            raise ValueError("Strava time offsets must be finite, nonnegative, and strictly increasing")
        if len(coord) != 2:
            raise ValueError("Invalid Strava coordinate")
        previous = offset
        point = SubElement(segment, "trkpt", {"lat": str(coord[0]), "lon": str(coord[1])})
        SubElement(point, "time").text = (start + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")
        if altitude is not None:
            SubElement(point, "ele").text = str(altitude[index])
    data = tostring(root, encoding="utf-8", xml_declaration=True)
    parse_gpx(data, "validation")
    return data


def sync_strava(activity_ids: list[int], output: Path, token: str | None = None):
    token = access_token(token)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for activity_id in activity_ids:
        if activity_id <= 0:
            raise ValueError("Activity IDs must be positive integers")
        activity = api_get(f"/activities/{activity_id}", token)
        if activity.get("sport_type", activity.get("type")) not in CYCLING_TYPES:
            raise ValueError("Selected activity is not a cycling ride")
        streams = api_get(f"/activities/{activity_id}/streams?keys=latlng,time,altitude&key_by_type=true", token)
        data = streams_to_gpx(activity, streams)
        file = output / f"strava-{activity_id}.gpx"
        file.write_bytes(data)
        results.append({"file": str(file), "bytes": len(data)})
    return results
