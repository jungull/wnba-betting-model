#!/usr/bin/env python3
"""Real-browser PDF fetch for the D033 injury live track — D048 authorized.

Uses a REAL, HEADED Chromium via Playwright (window positioned off-screen —
cosmetic only). The identity doctrine of fetch_official_report.py is
unchanged and this module is ruled consistent with it (D048): the client
genuinely IS a Chromium browser presenting its true default identity — no
User-Agent impersonation, no header forgery, no challenge solving.

Why headed, and why this shape (differential diagnosis, 2026-08-07, D048 +
ACCESS_VERIFICATION.md): ak-static.cms.nba.com resets/times-out every
script client AND headless Chromium (which honestly announces
HeadlessChrome; net::ERR_CONNECTION_RESET observed) while serving a headed
Chromium instantly. Navigating to a PDF in headed Chromium loads the
built-in viewer (response body is the viewer shell, not the file), so the
document bytes are obtained by a SAME-ORIGIN in-page fetch() after one
navigation establishes the origin — the browser's own network stack, the
page's genuine identity. Verified 2026-08-07: fetch status 200, 70,875
bytes, %PDF-1.4, Last-Modified carried.

Discipline carried over verbatim:
  - polite pacing: >= 1s between outbound requests (same 1 rps rule);
  - BotBlockDetected semantics: an explicit 401/403/429 or challenge-page
    marker STOPS everything — never worked around;
  - one shared browser/page per process (one navigation per process, then
    same-origin fetches), closed atexit;
  - a headed browser needs an interactive desktop session; when there is
    none (e.g. a scheduled task while logged out) launch fails and callers
    keep logging the honest urllib NETWORK_UNAVAILABLE — no silent gap.
"""
from __future__ import annotations

import atexit
import base64
import time
from datetime import datetime, timezone

_PLAYWRIGHT = None
_BROWSER = None
_PAGE = None
_ORIGIN_ESTABLISHED = False
_last_request_monotonic = [0.0]

_MIN_SPACING_SECONDS = 1.0
_NAV_TIMEOUT_MS = 45_000

_FETCH_JS = """async (u) => {
  const r = await fetch(u, {cache: 'no-store'});
  const buf = await r.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let s = '';
  for (let i = 0; i < bytes.length; i += 32768)
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + 32768));
  const hdrs = {};
  for (const [k, v] of r.headers.entries()) hdrs[k] = v;
  return {status: r.status, b64: btoa(s), headers: hdrs};
}"""


class BrowserFetchFailed(Exception):
    """The browser client also failed to obtain the document. Callers
    re-raise the ORIGINAL NetworkUnavailable so the logged condition stays
    the honest urllib observation."""


def _pace():
    elapsed = time.monotonic() - _last_request_monotonic[0]
    if elapsed < _MIN_SPACING_SECONDS:
        time.sleep(_MIN_SPACING_SECONDS - elapsed)
    _last_request_monotonic[0] = time.monotonic()


def _shutdown():
    global _PLAYWRIGHT, _BROWSER, _PAGE, _ORIGIN_ESTABLISHED
    try:
        if _BROWSER is not None:
            _BROWSER.close()
        if _PLAYWRIGHT is not None:
            _PLAYWRIGHT.stop()
    except Exception:
        pass
    _PLAYWRIGHT = _BROWSER = _PAGE = None
    _ORIGIN_ESTABLISHED = False


def _get_page(origin_url):
    """One headed browser + one page per process; the first call navigates
    to establish the target origin, subsequent calls reuse it."""
    global _PLAYWRIGHT, _BROWSER, _PAGE, _ORIGIN_ESTABLISHED
    if _PAGE is None:
        try:
            from playwright.sync_api import sync_playwright
            _PLAYWRIGHT = sync_playwright().start()
            # Genuine headed Chromium, default (honest) identity. The
            # off-screen window position is cosmetic, not identity.
            _BROWSER = _PLAYWRIGHT.chromium.launch(
                headless=False, args=["--window-position=-32000,-32000"])
            _PAGE = _BROWSER.new_context().new_page()
            atexit.register(_shutdown)
        except Exception as e:
            _shutdown()
            raise BrowserFetchFailed(f"browser launch failed: {e}") from e
    if not _ORIGIN_ESTABLISHED:
        from playwright.sync_api import Error as PlaywrightError
        try:
            _PAGE.goto(origin_url, timeout=_NAV_TIMEOUT_MS)
            _ORIGIN_ESTABLISHED = True
        except PlaywrightError as e:
            raise BrowserFetchFailed(f"origin navigation failed: {e}") from e
    return _PAGE


def fetch_pdf_via_browser(url):
    """Fetch one PDF with real headed Chromium (same-origin in-page fetch).
    Returns (body_bytes, retrieval_ts_utc_iso, status_code, headers_dict).
    Raises BrowserFetchFailed on failure, or
    fetch_official_report.BotBlockDetected on an explicit block signature
    (which callers must NOT convert into a retry)."""
    from fetch_official_report import BotBlockDetected, _CHALLENGE_MARKERS

    _pace()
    page = _get_page(url)
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    try:
        out = page.evaluate(_FETCH_JS, url)
    except Exception as e:
        raise BrowserFetchFailed(f"in-page fetch failed: {e}") from e
    status = int(out.get("status") or 0)
    body = base64.b64decode(out.get("b64") or "")
    headers = {k.title(): v for k, v in (out.get("headers") or {}).items()}
    if status in (401, 403, 429):
        raise BotBlockDetected(url, status,
                                "explicit block status observed by browser client")
    if not body.startswith(b"%PDF"):
        head = body[:4096].lower()
        for marker in _CHALLENGE_MARKERS:
            if marker in head:
                raise BotBlockDetected(url, status,
                                        f"challenge marker in body: {marker!r}")
        raise BrowserFetchFailed(
            f"response is not a PDF (status {status}, first bytes {body[:8]!r})")
    return body, retrieval_ts, status, headers
