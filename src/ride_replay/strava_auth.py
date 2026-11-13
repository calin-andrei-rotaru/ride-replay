"""One-session Strava OAuth on loopback. Credentials are never persisted."""
import getpass
import json
import os
import re
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

TOKEN_URL = "https://www.strava.com/oauth/token"


def callback_code(path: str, state: str, required_scope: str) -> str:
    parsed = urlsplit(path)
    values = parse_qs(parsed.query, keep_blank_values=True)
    received = values.get("state", [])
    if parsed.path != "/callback" or len(received) != 1 or not secrets.compare_digest(received[0].encode(), state.encode()):
        raise ValueError("Invalid authorization callback state")
    if "error" in values:
        raise ValueError("Strava authorization was declined; no rides were imported")
    codes, scopes = values.get("code", []), values.get("scope", [])
    if len(scopes) != 1 or required_scope not in set(re.split(r"[,\s]+", scopes[0])):
        raise ValueError("Required activity read scope was not granted; authorize again")
    if len(codes) != 1 or not re.fullmatch(r"[A-Za-z0-9._~-]+", codes[0]):
        raise ValueError("Strava did not return a usable authorization code")
    return codes[0]


def exchange_code(client_id: str, client_secret: str, code: str) -> str:
    body = urlencode({"client_id": client_id, "client_secret": client_secret,
        "code": code, "grant_type": "authorization_code"}).encode()
    request = Request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read(65_537)
    except HTTPError as error:
        raise ValueError(f"Strava token exchange failed (HTTP {error.code}); check your API app credentials and authorize again") from None
    if len(data) > 65_536:
        raise ValueError("Strava token response exceeds size limit")
    try:
        token = json.loads(data)["access_token"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("Strava returned an invalid token response") from None
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~-]+", token):
        raise ValueError("Strava returned an unusable access token")
    return token


def authorize_strava(*, include_private=False, timeout=300) -> str:
    client_id = os.environ.get("STRAVA_CLIENT_ID") or input("Strava API client ID: ").strip()
    secret = os.environ.get("STRAVA_CLIENT_SECRET") or getpass.getpass("Strava API client secret (hidden): ")
    if not re.fullmatch(r"[0-9]+", client_id) or int(client_id) <= 0:
        raise ValueError("Strava client ID must be a positive integer")
    if not secret or not re.fullmatch(r"[A-Za-z0-9._~-]+", secret):
        raise ValueError("Enter the API client secret without whitespace")
    scope = "activity:read_all" if include_private else "activity:read"
    state = secrets.token_urlsafe(32)
    outcome = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            # The request URL contains a one-time authorization code.
            pass

        def do_GET(self):
            status = 200
            try:
                code = callback_code(self.path, state, scope)
                outcome["code"] = code
                message = "Authorization received. Return to the Ride Replay terminal to finish importing."
            except ValueError as error:
                status = 400
                message = str(error)
                # Stray/forged requests must not consume the pending login.
                if message != "Invalid authorization callback state":
                    outcome["error"] = message
            content = message.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

    with HTTPServer(("127.0.0.1", 0), CallbackHandler) as server:
        server.timeout = 1
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        url = "https://www.strava.com/oauth/authorize?" + urlencode({"client_id": client_id,
            "redirect_uri": redirect, "response_type": "code", "approval_prompt": "force",
            "scope": scope, "state": state})
        print("Authorize Ride Replay in your browser. Credentials remain in this process and are not saved.")
        print(f"If the browser does not open, visit: {url}")
        deadline = time.monotonic() + timeout
        webbrowser.open(url)
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
    if "error" in outcome:
        raise ValueError(outcome["error"])
    if "code" not in outcome:
        raise ValueError("Strava authorization timed out; rerun the command when ready")
    return exchange_code(client_id, secret, outcome["code"])
