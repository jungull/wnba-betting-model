# Access verification -- D032/D033 official injury report, live track

Performed fresh this session (2026-08-06, replacing an earlier run on this
same track whose README made claims not reproduced here -- see
"Note on the prior run" at the bottom). Every test below was run by this
node directly, with commands and raw results as shown; nothing here is
relayed from the prior README without independent reproduction.

**Client identity used throughout:** `User-Agent:
WNBA-Research-Bot/1.0 (contact: jgallagher@sasscpas.com; D033 injury-live
track, polite 1rps, honest UA, no bypass of bot mitigation)` -- the same
honest, project-identifying, non-browser-spoofing UA the D033 history track
used for its Wayback CDX work. No JavaScript execution, no header forgery,
no CAPTCHA/challenge solving was attempted anywhere in this session.

## 1. `www.wnba.com/wnba-injury-report` (human-readable report page)

**PowerShell `Invoke-WebRequest -UseBasicParsing`, this session:**
`HTTP 200`. Response carries `X-Powered-By: Next.js`, an Akamai
`_abck` anti-bot cookie, and standard CDN headers -- **not** a
challenge/CAPTCHA page.

This **contradicts** the earlier `FREE_DATA_SURVEY/MARKET_SOURCES.md`
finding of `HTTP 403` against `wnba.com/robots.txt` and the scoreboard-class
endpoints. Not adjudicated as "the earlier survey was wrong" -- the earlier
403s were against different specific URLs (`robots.txt`, not this page),
tested from what may be a different environment/IP at a different time.
Reported as-is: **this specific URL, from this sandbox, right now, with a
plain honest GET, returns 200.**

## 2. `www.wnba.com/api/injury-reports` (backing JSON, the actual discovery
target)

**PowerShell, this session:** `HTTP 200`. Body is real JSON:
`{"dateLabel": "August 6", "links": [{"href":
"https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_2026-08-06_12_00AM.pdf",
"label": "12:00 a.m. ET report"}, ... 62 entries at first check, growing to
63 an hour later ...]}`. Consecutive labels are exactly 15 minutes apart
(`12:00 a.m.`, `12:15 a.m.`, `12:30 a.m.`, ...) for the **current ET
calendar day only** -- this independently reproduces, from live bytes, the
D033 history track's Wayback-derived finding that
`wnba.com/api/injury-reports` exists and is a quarter-hour discovery feed,
and additionally proves it is **currently reachable live**, which the
history track's Wayback-only method could not test.

**Re-verified from Python** (`urllib.request`, stdlib, no `requests`, no
browser UA) in this module's own `fetch_official_report.py`: also `200`,
`63` links. Two independent HTTP clients, two independent language
runtimes, same result.

**Conclusion: not blocked.** This resolves the mandate's open question --
"verify current accessibility HONESTLY from a script client ... if still
blocked, document status codes and STOP" -- the answer is it is
**currently accessible**, not blocked, from both a polite Python client and
PowerShell.

## 3. `ak-static.cms.nba.com/referee/wnba_injury/*.pdf` (the actual report
documents, linked from #2)

This is a **different host** from #1/#2 (an Akamai-fronted static CDN, not
`wnba.com` itself) and is where the actual verification diverges from
"blocked" into something else entirely:

| method | result |
|---|---|
| DNS resolution (`Resolve-DnsName`) | resolves cleanly to Akamai edge (`e12399.dsce2.akamaiedge.net`, both A and AAAA) |
| TCP connect, port 443 (`Test-NetConnection`) | **succeeds** (`TcpTestSucceeded: True`) |
| PowerShell `Invoke-WebRequest` GET | timeout, no HTTP status returned |
| PowerShell `Invoke-WebRequest` HEAD, 3 attempts, 2s apart | timeout every time, no HTTP status |
| `curl.exe` GET | `curl: (56) Recv failure: Connection was reset` -- TLS/TCP connects, then resets mid-transfer, `HTTP_CODE:000` |
| .NET `HttpClient.GetAsync` (explicit TLS 1.2) | `A task was canceled` (timeout) |
| Python `urllib.request` (stdlib, this module's actual fetch path, `fetch_official_report.fetch_pdf`) | `TimeoutError: The read operation timed out` |

**Five independent attempts, four different HTTP client implementations
(PowerShell/WinHTTP, curl/libcurl, .NET HttpClient, Python urllib),
consistent result: the TCP handshake succeeds but the HTTP layer never
returns a status code** -- no 403, no 429, no challenge-page body, no
CAPTCHA. This is **not** the bot-block signature this track's
`fetch_official_report.BotBlockDetected` is built to catch (which requires
an actual HTTP status or a challenge-page body marker); it is classified
`NetworkUnavailable` and reported as a **sandbox egress condition specific
to this CDN host**, not a confirmed host-side block, per the mandate's
instruction not to over-claim a block that wasn't observed.

**Corroborating context, read-only from the live main worktree (never
modified by this track):** `injury_capture_daily.py`'s own production
archive (`data/injury_capture/raw/`) holds a real, continuous,
hours-old-as-of-this-session run of successful captures against this exact
same host (`wnba_official_20260806T190009Z.pdf`, retrieved at 19:00:09Z,
about 30 minutes before this track's own attempts began failing). This
means the host itself is not categorically unreachable -- production
capture from elsewhere in this program's infrastructure was working on
this same day -- which supports "sandbox-specific egress condition" over
"host now blocks everyone", but does not prove it (no controlled A/B was
possible with only this sandbox's own network path available to this
node).

**Per the mandate: reported, not bypassed. No attempt was made to spoof a
browser UA, add extra headers, or otherwise work around this**, on either
the CDN host or the (unblocked) `wnba.com` JSON host.

## Net assessment

- `wnba.com/wnba-injury-report` and `wnba.com/api/injury-reports`: **NOT
  blocked** in this session, from this sandbox, with a plain honest client.
  This is the actionable discovery mechanism this track's
  `fetch_official_report.fetch_discovery_json()` uses.
- `ak-static.cms.nba.com` (the PDF documents themselves): **not
  confirmed blocked** (no 403/429/challenge observed anywhere), but **not
  reachable this session** from this sandbox specifically (TCP connects,
  HTTP layer never completes, across 5 attempts / 4 client
  implementations). Classified and logged as `NETWORK_UNAVAILABLE`, a
  distinct, retryable outcome from `BOT_BLOCK` in `capture_log.csv`.
- Consequence: **one live capture cycle could not be completed this
  session** -- `capture_injury_live.py` was run for real against the real
  discovery JSON, attempted a real PDF fetch, and honestly logged
  `NETWORK_UNAVAILABLE` in `capture_log.csv` (see that file; the row is
  real, not fabricated). The module, parser, dedup, supersession, and
  absent-row-rule logic are fully built and are verified by 12 passing
  fixture tests (`tests/`) against real production PDF bytes sourced
  read-only from this program's own existing archive -- see
  `tests/fixtures/PROVENANCE.md`. Recommend the coordinator's first
  scheduled run retry the PDF fetch; if `NETWORK_UNAVAILABLE` persists
  across a scheduled (non-sandbox) execution environment, that would be new
  evidence worth escalating; if it clears, no further action is needed.

## Note on the prior run

An earlier version of this track's README made claims (three `HEAD`
probes succeeding against `ak-static.cms.nba.com` with 200s and matching
ETags/Last-Modified) that could not be independently reproduced by this
node under the same host this session -- this track's own five attempts,
above, all failed at the HTTP layer against that host. This is recorded as
a discrepancy, not resolved as fraud vs. transient host behavior: it is
consistent with genuinely intermittent egress to this specific CDN (the
prior README's own §4 already reported *later* attempts in that same
session timing out after its initial probes succeeded), and this session's
attempts happened to fall entirely in a failing window. It is **not**
treated as license to relay the prior claims uncritically -- every claim
in this document was re-tested from scratch, and this document reports
only what was directly observed this session.
