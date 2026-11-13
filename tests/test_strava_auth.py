import io
import threading
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

import pytest

from ride_replay import strava_auth


@pytest.mark.parametrize("query,reason", [
    ({"state": "forged", "code": "private-code", "scope": "activity:read"}, "state"),
    ({"state": "✓", "code": "private-code", "scope": "activity:read"}, "state"),
    ({"state": "expected", "error": "access_denied"}, "declined"),
    ({"state": "expected", "code": "private-code", "scope": "read"}, "scope"),
    ({"state": "expected", "code": "<private-code>", "scope": "activity:read"}, "code"),
])
def test_callback_rejects_untrusted_state_denial_and_missing_scope(query, reason):
    with pytest.raises(ValueError, match=reason) as error:
        strava_auth.callback_code("/callback?" + urlencode(query), "expected", "activity:read")
    assert "private-code" not in str(error.value)


def test_callback_accepts_exact_scope_and_rejects_duplicate_parameters():
    assert strava_auth.callback_code("/callback?state=expected&code=abc&scope=read,activity:read", "expected", "activity:read") == "abc"
    for query in ("state=expected&state=forged&code=abc&scope=activity:read", "state=expected&code=abc&code=def&scope=activity:read"):
        with pytest.raises(ValueError):
            strava_auth.callback_code("/callback?" + query, "expected", "activity:read")


def test_token_exchange_posts_secret_and_does_not_echo_it(monkeypatch):
    def fake_open(request, timeout):
        assert request.full_url == "https://www.strava.com/oauth/token"
        assert request.method == "POST"
        assert "client-secret" not in request.full_url
        assert parse_qs(request.data.decode())["client_secret"] == ["client-secret"]
        return io.BytesIO(b'{"access_token":"session-token","refresh_token":"discarded"}')
    monkeypatch.setattr(strava_auth, "urlopen", fake_open)
    assert strava_auth.exchange_code("123", "client-secret", "one-time-code") == "session-token"

    def failed_open(request, timeout):
        raise HTTPError(request.full_url, 400, "private-code", {}, None)
    monkeypatch.setattr(strava_auth, "urlopen", failed_open)
    with pytest.raises(ValueError, match="HTTP 400") as error:
        strava_auth.exchange_code("123", "client-secret", "one-time-code")
    assert "client-secret" not in str(error.value) and "private-code" not in str(error.value)


def test_loopback_login_ignores_forgery_and_exchanges_once(monkeypatch, capsys):
    monkeypatch.setenv("STRAVA_CLIENT_ID", "123")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "client-secret")
    seen, failures, threads = {}, [], []

    def browser_open(url):
        assert url.startswith("https://www.strava.com/oauth/authorize?")
        params = parse_qs(urlsplit(url).query)
        redirect = params["redirect_uri"][0]
        assert urlsplit(redirect).hostname == "127.0.0.1"
        assert params["scope"] == ["activity:read_all"]
        seen["redirect"] = redirect

        def callback():
            try:
                try:
                    urlopen(redirect + "?" + urlencode({"state": "forged", "code": "bad-code", "scope": "activity:read_all"}), timeout=5)
                    raise AssertionError("Forged callback accepted")
                except HTTPError as error:
                    assert error.code == 400
                with urlopen(redirect + "?" + urlencode({"state": params["state"][0], "code": "one-time-code", "scope": "activity:read_all"}), timeout=5) as response:
                    assert response.status == 200
                    assert response.headers["Cache-Control"] == "no-store"
                    assert b"one-time-code" not in response.read()
            except Exception as error:
                failures.append(error)
        thread = threading.Thread(target=callback)
        threads.append(thread)
        thread.start()
        return True

    def exchange(client_id, secret, code):
        assert (client_id, secret, code) == ("123", "client-secret", "one-time-code")
        return "session-token"

    monkeypatch.setattr(strava_auth.webbrowser, "open", browser_open)
    monkeypatch.setattr(strava_auth, "exchange_code", exchange)
    assert strava_auth.authorize_strava(include_private=True, timeout=5) == "session-token"
    for thread in threads:
        thread.join(timeout=5)
    assert not failures
    output = capsys.readouterr().out
    assert all(secret not in output for secret in ("client-secret", "one-time-code", "session-token"))
    with pytest.raises(OSError):
        urlopen(seen["redirect"], timeout=1)
