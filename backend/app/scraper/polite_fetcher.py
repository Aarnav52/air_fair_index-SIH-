"""
PoliteFetcher: the shared, compliance-first HTTP fetch layer every
source-specific adapter must go through - no adapter gets its own direct
requests (per CODING_AGENT_CONTEXT.md's spec).

Built step by step. This file now covers all four required pieces:
robots.txt enforcement, bot-challenge detection, per-host rate limiting,
and the circuit breaker - all routed through the same request path.
"""

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests


class RequestsTransport:
    """Production transport - real HTTP via the requests library. A real
    network failure (timeout, connection error, TLS handshake failure -
    the exact shape seen against IndiGo/Air India during legality
    research) is not caught here; it propagates to _do_request, which
    records it as a circuit-breaker failure. Never retried at this layer."""

    def __init__(self, timeout_seconds=15):
        self._timeout_seconds = timeout_seconds

    def get(self, url, headers=None):
        response = requests.get(url, headers=headers, timeout=self._timeout_seconds)
        return FetchResult(
            url, response.status_code, response.text, dict(response.headers)
        )


class PlaywrightTransport:
    """Production transport - a real Chromium browser via Playwright, for
    sites that TLS-fingerprint requests/curl and reset the connection
    before the handshake even completes (confirmed against Akasa Air and
    SpiceJet - raw TCP connects fine, but the TLS ClientHello itself gets
    reset). This is not an anti-detection technique: no automation-hiding
    flags are set (no --disable-blink-features=AutomationControlled, no
    proxy, no fingerprint spoofing) - it presents exactly what a real
    Chromium browser presents, because it is one. If a site's defenses
    are sophisticated enough to detect and block even this, that block is
    respected the same as any other bot-challenge, not worked around.

    playwright is imported lazily so the rest of this module doesn't
    require it just to use RequestsTransport.

    Launches one browser at construction and reuses it; call close() when
    done with it.

    After get(), the page used for that fetch is kept open on
    self.last_page - so a caller doing a real search flow (fill a form,
    click, wait for results) can go through PoliteFetcher.fetch() for the
    compliance-gated initial navigation (robots.txt, rate limit, circuit
    breaker all apply), then continue interacting with that SAME,
    already-permitted page directly, instead of the interactive part
    silently bypassing the compliance layer with its own raw Playwright
    session. Contexts accumulate until close() tears down the whole
    browser - fine for a short-lived scrape run, not meant for a
    long-running process making many fetches."""

    def __init__(self, timeout_seconds=15):
        from playwright.sync_api import sync_playwright

        self._timeout_ms = timeout_seconds * 1000
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self.last_page = None

    def get(self, url, headers=None):
        context = self._browser.new_context(extra_http_headers=headers or {})
        page = context.new_page()
        try:
            response = page.goto(url, timeout=self._timeout_ms)
        except Exception:
            context.close()
            raise
        status_code = response.status if response else 0
        text = page.content()
        self.last_page = page
        return FetchResult(url, status_code, text, dict(response.headers) if response else {})

    def close(self):
        self._browser.close()
        self._playwright.stop()


class RealClock:
    """Production clock - wall-clock time.monotonic() and a real sleep()."""

    def now(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)


class RobotsDisallowedError(Exception):
    """robots.txt policy disallows this URL. Never caught and retried - abort."""


class BotChallengeDetectedError(Exception):
    """Response looks like a bot-challenge or block. Never solved, never
    retried, never evaded - abort immediately."""


class CircuitOpenError(Exception):
    """Too many consecutive failures on this host recently - refusing to
    even attempt another request until the cooldown passes. This is what
    "stops hammering it" means: no transport call happens at all while
    the circuit is open, not even one that's expected to fail."""


_BOT_CHALLENGE_STATUS_CODES = {403, 429, 503}

_BOT_CHALLENGE_MARKERS = (
    "captcha",
    "unusual traffic",
    "checking your browser",
    "cloudflare",
    "incapsula",
    "are you a human",
    "please verify you are a human",
    "distil",
    "perimeterx",
)


def _looks_like_bot_challenge(result):
    if result.status_code in _BOT_CHALLENGE_STATUS_CODES:
        return True
    lowered = (result.text or "").lower()
    return any(marker in lowered for marker in _BOT_CHALLENGE_MARKERS)


class FetchResult:
    def __init__(self, url, status_code, text, headers=None):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class PoliteFetcher:
    """
    Every fetch goes through fetch(). robots.txt is checked before every
    request, fetched via the exact same transport call as any other URL -
    never a library's own auto-fetching reader (RobotFileParser.read()
    makes its own separate network call, silently bypassing whatever
    accounting a shared fetch path does - the gotcha CODING_AGENT_CONTEXT.md
    calls out explicitly).

    There is no way to disable the robots.txt check: no constructor
    parameter exists for it. Passing one anyway raises TypeError, Python's
    ordinary behavior for an unexpected keyword argument - not a config
    flag that could be flipped on by mistake.

    Rate limiting is tracked per host, not globally - a slow or blocked
    host must not throttle requests to a different, working one. It
    applies to every actual network call, robots.txt fetches included,
    since those go to the same host too.

    The circuit breaker is also per host: after `failure_threshold`
    consecutive failures (a transport exception, or a detected
    bot-challenge) it opens for `circuit_reset_timeout` seconds, refusing
    every request to that host with no transport call at all. After the
    cooldown, exactly one trial request is allowed through; success
    closes the circuit (failure count resets to zero), failure re-opens
    it and restarts the cooldown.
    """

    def __init__(self, transport, clock=None, min_request_interval=1.0,
                 failure_threshold=3, circuit_reset_timeout=30.0):
        self._transport = transport
        self._clock = clock or RealClock()
        self._min_request_interval = min_request_interval
        self._failure_threshold = failure_threshold
        self._circuit_reset_timeout = circuit_reset_timeout
        self._robots_cache = {}  # host -> urllib.robotparser.RobotFileParser
        self._last_request_time = {}  # host -> clock.now() at last request
        self._consecutive_failures = {}  # host -> int
        self._circuit_opened_at = {}  # host -> clock.now() when it opened

    def _robots_url(self, host):
        return f"https://{host}/robots.txt"

    def _enforce_rate_limit(self, host):
        last = self._last_request_time.get(host)
        now = self._clock.now()
        if last is not None:
            wait = self._min_request_interval - (now - last)
            if wait > 0:
                self._clock.sleep(wait)
                now = self._clock.now()
        self._last_request_time[host] = now

    def _check_circuit(self, host):
        opened_at = self._circuit_opened_at.get(host)
        if opened_at is None:
            return  # circuit closed - nothing to check
        if self._clock.now() - opened_at < self._circuit_reset_timeout:
            raise CircuitOpenError(
                f"circuit open for {host}: {self._consecutive_failures[host]} "
                f"consecutive failures, cooldown not yet elapsed"
            )
        # Cooldown elapsed - allow exactly one trial request through
        # (half-open). Failure count stays as-is until that trial
        # actually succeeds or fails.

    def _record_success(self, host):
        self._consecutive_failures.pop(host, None)
        self._circuit_opened_at.pop(host, None)

    def _record_failure(self, host):
        count = self._consecutive_failures.get(host, 0) + 1
        self._consecutive_failures[host] = count
        if count >= self._failure_threshold:
            self._circuit_opened_at[host] = self._clock.now()

    def _do_request(self, url, user_agent):
        """The one place that actually calls the transport. Every fetch -
        robots.txt included - goes through here, so rate limiting,
        bot-challenge detection, and the circuit breaker all apply
        uniformly rather than only to "real" content fetches.

        Sends the exact same user_agent that robots.txt was checked
        against - checking one identity's rules while presenting as a
        different one to the actual server would be a real compliance
        bug, not just an inconsistency."""
        host = urlparse(url).netloc.lower()
        self._check_circuit(host)  # before rate limiting - no point
        self._enforce_rate_limit(host)  # waiting to reject a request anyway

        try:
            result = self._transport.get(url, headers={"User-Agent": user_agent})
        except Exception:
            self._record_failure(host)
            raise

        if _looks_like_bot_challenge(result):
            self._record_failure(host)
            raise BotChallengeDetectedError(
                f"bot-challenge detected fetching {url} (status={result.status_code})"
            )

        self._record_success(host)
        return result

    def _get_robots_parser(self, host, user_agent):
        if host in self._robots_cache:
            return self._robots_cache[host]

        result = self._do_request(self._robots_url(host), user_agent)
        parser = urllib.robotparser.RobotFileParser()

        if result.status_code == 200:
            # .parse() on text we fetched ourselves - never .read(), which
            # would fetch again on its own and skip our request path.
            parser.parse(result.text.splitlines())
        elif result.status_code == 401:
            # Access denied to robots.txt itself (but not a bot-challenge
            # status - those already raised above): treat as disallowed,
            # not as wide open.
            parser.disallow_all = True
        else:
            # No robots.txt published (404 etc.) = no rules = allowed.
            parser.allow_all = True

        self._robots_cache[host] = parser
        return parser

    def fetch(self, url, user_agent="APIx-PoliteFetcher/1.0"):
        # Hostnames are case-insensitive; lowercase before caching so
        # Example.com and example.com share one robots.txt fetch.
        host = urlparse(url).netloc.lower()
        if not host:
            raise ValueError(f"invalid URL: no host found in {url!r}")
        parser = self._get_robots_parser(host, user_agent)

        if not parser.can_fetch(user_agent, url):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

        return self._do_request(url, user_agent)
