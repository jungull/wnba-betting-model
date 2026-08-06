#!/usr/bin/env python3
"""
Network layer for the D032/D033 official injury-report live track.

Two hosts, verified independently this session (see ACCESS_VERIFICATION.md
for the full honest record, including what did NOT work):

  1. https://www.wnba.com/api/injury-reports  -- discovery. Confirmed
     reachable (HTTP 200) from this sandbox with a plain, honest,
     non-browser-spoofing GET. Returns JSON: {"dateLabel": "...",
     "links": [{"href": "<pdf url>", "label": "<H:MM a.m./p.m. ET
     report>"}, ...]} for the CURRENT ET calendar day only, confirming the
     quarter-hour publishing cadence exactly (distinct 15-minute-labeled
     links) and giving the authoritative set of report URLs -- this is a
     materially better discovery mechanism than guessing/walking back
     15-minute slot labels, because it is the source enumerating its own
     documents rather than us probing for their existence.

  2. https://ak-static.cms.nba.com/referee/wnba_injury/
     Injury-Report_{YYYY-MM-DD}_{H_MM}{AM|PM}.pdf -- the actual PDF
     documents, linked from (1). TCP connects (verified: DNS resolves to
     Akamai edge, port 443 handshake succeeds), but every HTTP request this
     session (GET and HEAD, via three independent clients: PowerShell
     Invoke-WebRequest, curl.exe, .NET HttpClient) timed out or reset with
     NO HTTP status code returned at all -- not a 403, not a challenge
     page, not a CAPTCHA. This is reported honestly as
     NETWORK_UNAVAILABLE, distinct from a confirmed bot-block signature,
     because no such signature was observed; it is NOT worked around, per
     standing rules, regardless of which category it turns out to be.

This module never spoofs identity to get past a block: no browser
User-Agent impersonation, no header forgery, no JS/challenge solving. The
User-Agent below names this project and a contact address, honestly.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = ("WNBA-Research-Bot/1.0 "
              "(contact: jgallagher@sasscpas.com; D033 injury-live track, "
              "polite 1rps, honest UA, no bypass of bot mitigation)")

DISCOVERY_URL = "https://www.wnba.com/api/injury-reports"
MIN_REQUEST_SPACING_SECONDS = 1.0  # "polite client (1 rps)" per mandate

_BOT_BLOCK_STATUS_CODES = {401, 403, 429}
_CHALLENGE_MARKERS = (
    b"captcha", b"cf-challenge", b"cloudflare", b"access denied",
    b"perimeterx", b"__cf_chl", b"px-captcha", b"are you a human",
)


class BotBlockDetected(Exception):
    """Raised when the response carries an explicit bot-mitigation
    signature (401/403/429 status, or a challenge-page body marker).
    Per standing rules: report and STOP. Never spoof headers, solve a
    challenge, or otherwise work around this."""

    def __init__(self, url, status_code, detail):
        self.url = url
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"bot-block-shaped response from {url}: "
                          f"status={status_code} detail={detail}")


class NetworkUnavailable(Exception):
    """Connection-level failure (timeout, reset, DNS) with NO HTTP status
    code returned at all. Distinct from BotBlockDetected: this is reported
    as a network condition, not asserted to be a host-side block, because
    no block signature was observed. Retryable on a later scheduled
    cycle."""

    def __init__(self, url, reason):
        self.url = url
        self.reason = reason
        super().__init__(f"network-unavailable fetching {url}: {reason}")


@dataclass
class FetchResult:
    url: str
    status_code: int
    body: bytes
    headers: dict = field(default_factory=dict)
    retrieval_ts_utc: str = ""


_last_request_monotonic = [0.0]


def _pace():
    """Enforce >=1s spacing between outbound requests (polite 1rps)."""
    elapsed = time.monotonic() - _last_request_monotonic[0]
    if elapsed < MIN_REQUEST_SPACING_SECONDS:
        time.sleep(MIN_REQUEST_SPACING_SECONDS - elapsed)
    _last_request_monotonic[0] = time.monotonic()


def _get(url, timeout=20):
    from datetime import datetime, timezone
    _pace()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
            headers = dict(resp.headers.items())
    except urllib.error.HTTPError as e:
        body = e.read() or b""
        status = e.code
        headers = dict(e.headers.items()) if e.headers else {}
        if status in _BOT_BLOCK_STATUS_CODES:
            raise BotBlockDetected(url, status, body[:300])
        return FetchResult(url, status, body, headers, retrieval_ts)
    except (urllib.error.URLError, TimeoutError, ConnectionError,
            OSError) as e:
        raise NetworkUnavailable(url, f"{type(e).__name__}: {e}")

    lowered = body[:4000].lower()
    if any(marker in lowered for marker in _CHALLENGE_MARKERS):
        raise BotBlockDetected(url, status, "challenge-page body marker")
    return FetchResult(url, status, body, headers, retrieval_ts)


def fetch_discovery_json():
    """GET the day's official report-link discovery JSON.
    -> (FetchResult, parsed_dict). Raises BotBlockDetected /
    NetworkUnavailable on failure -- never falls back to guessing slots
    silently; the caller decides what "no discovery" means for this cycle.
    """
    result = _get(DISCOVERY_URL)
    if result.status_code != 200:
        raise NetworkUnavailable(
            DISCOVERY_URL, f"non-200 without bot-block signature: "
                           f"{result.status_code}")
    parsed = json.loads(result.body.decode("utf-8"))
    return result, parsed


def fetch_pdf(url, retries=2, backoff_seconds=3.0):
    """GET a report PDF. Retries only on NetworkUnavailable (transient);
    never retries around a BotBlockDetected -- that propagates immediately,
    per standing rules (report, don't bypass, don't hammer a blocking
    host)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            return _get(url, timeout=30)
        except NetworkUnavailable as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff_seconds * (attempt + 1))
                continue
            raise
        except BotBlockDetected:
            raise
    raise last_err  # pragma: no cover
