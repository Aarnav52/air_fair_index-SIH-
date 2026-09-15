"""
Self-check for PoliteFetcher step 1 (robots.txt enforcement).
Plain asserts, no framework, no real network - a FakeTransport stands in
for HTTP. Run directly: python test_polite_fetcher.py
"""

from app.scraper.polite_fetcher import (
    PoliteFetcher,
    RobotsDisallowedError,
    BotChallengeDetectedError,
    CircuitOpenError,
    FetchResult,
)


class FakeClock:
    """Controllable time - never a real sleep(). sleep() just advances
    the fake clock forward by that amount and records the call."""

    def __init__(self, start=1000.0):
        self._now = start
        self.sleep_calls = []

    def now(self):
        return self._now

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)
        self._now += seconds


class FakeTransport:
    """Canned responses keyed by exact URL. Records every call made, so
    tests can prove robots.txt goes through this same path, not some
    separate hidden fetch.

    A value may be a single FetchResult/Exception (always returned/raised
    the same way), or a list of them consumed in order - once only one
    item remains, it keeps being returned/raised as the steady state, so
    a test can queue e.g. [fail, fail, success] for circuit-breaker
    scenarios without running out."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, headers=None):
        self.calls.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected fetch: {url}")
        value = self.responses[url]
        if isinstance(value, list):
            item = value.pop(0) if len(value) > 1 else value[0]
        else:
            item = value
        if isinstance(item, Exception):
            raise item
        return item


def test_disallowed_path_raises():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200,
            "User-agent: *\nDisallow: /private/\n",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/private/secret")
        raise AssertionError("expected RobotsDisallowedError")
    except RobotsDisallowedError:
        pass


def test_allowed_path_succeeds():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200,
            "User-agent: *\nDisallow: /private/\n",
        ),
        "https://example.com/public/page": FetchResult(
            "https://example.com/public/page", 200, "hello",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    result = fetcher.fetch("https://example.com/public/page")
    assert result.text == "hello"


def test_robots_txt_fetched_through_same_transport():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 200, "ok",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    fetcher.fetch("https://example.com/page")
    assert transport.calls == [
        "https://example.com/robots.txt",
        "https://example.com/page",
    ], transport.calls


def test_robots_txt_cached_not_refetched():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/a": FetchResult("https://example.com/a", 200, "a"),
        "https://example.com/b": FetchResult("https://example.com/b", 200, "b"),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    fetcher.fetch("https://example.com/a")
    fetcher.fetch("https://example.com/b")
    robots_fetches = [c for c in transport.calls if c.endswith("/robots.txt")]
    assert len(robots_fetches) == 1, robots_fetches


def test_missing_robots_txt_means_allowed():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 404, "",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 200, "ok",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    result = fetcher.fetch("https://example.com/page")
    assert result.text == "ok"


def test_robots_txt_401_means_disallow_all():
    # 401 isn't one of the bot-challenge status codes (403/429/503) - it's
    # a distinct "access denied" signal, handled as a robots.txt policy
    # matter, not a bot-challenge.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 401, "",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/anything")
        raise AssertionError("expected RobotsDisallowedError")
    except RobotsDisallowedError:
        pass


def test_robots_txt_403_is_a_bot_challenge_not_a_policy_disallow():
    # 403 IS one of the named bot-challenge status codes - getting blocked
    # while fetching robots.txt itself is a different situation than the
    # site's policy saying no, and must be distinguished.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 403, "",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/anything")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass


def test_bot_challenge_status_code_raises_and_is_not_retried():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 429, "slow down",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass
    page_fetches = [c for c in transport.calls if c == "https://example.com/page"]
    assert len(page_fetches) == 1, "must not retry after a bot-challenge"


def test_bot_challenge_text_marker_raises_even_on_200():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 200,
            "<html>Please complete the CAPTCHA to continue</html>",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass


def test_503_status_code_is_a_bot_challenge():
    # 429 is already covered above; 503 is separately named in the spec
    # and must be checked explicitly, not assumed to work by similarity.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 503, "service unavailable",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass


def test_403_on_content_fetch_is_also_a_bot_challenge():
    # Distinct from the robots.txt-specific 403 test above - confirms the
    # same detection applies to the actual content fetch, not just robots.txt.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 403, "forbidden",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass


def test_cloudflare_marker_detected():
    # Spot-check a second marker, not just "captcha" - confirms the list
    # is actually wired in, not just the detection mechanism in the abstract.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 200,
            "<html>Checking your browser before accessing... Cloudflare</html>",
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected BotChallengeDetectedError")
    except BotChallengeDetectedError:
        pass


def test_hostname_case_is_normalized_for_robots_cache():
    # Example.com and example.com must share one robots.txt fetch, not be
    # treated as different hosts.
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://Example.com/a": FetchResult("https://Example.com/a", 200, "a"),
        "https://example.com/b": FetchResult("https://example.com/b", 200, "b"),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    fetcher.fetch("https://Example.com/a")
    fetcher.fetch("https://example.com/b")
    robots_fetches = [c for c in transport.calls if c.endswith("/robots.txt")]
    assert len(robots_fetches) == 1, robots_fetches


def test_transport_exception_propagates_uncaught():
    # Documents current, deliberate behavior: a real network failure (the
    # same shape as the IndiGo/Air India TLS-timeout case found during
    # legality research) is not swallowed or silently retried here - it
    # propagates as-is. Turning "propagates" into "opens the circuit
    # breaker after N of these" is step 4's job, not this one's.
    class FailingTransport:
        def get(self, url, headers=None):
            raise ConnectionError("simulated network failure")

    fetcher = PoliteFetcher(FailingTransport())
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected ConnectionError to propagate")
    except ConnectionError:
        pass


def test_malformed_url_raises_value_error_fast():
    transport = FakeTransport({})
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    try:
        fetcher.fetch("not-a-real-url")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert transport.calls == [], "must fail before ever touching the network"


def test_none_text_does_not_crash_bot_challenge_check():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 200, None,
        ),
    })
    fetcher = PoliteFetcher(transport, min_request_interval=0)
    result = fetcher.fetch("https://example.com/page")
    assert result.text is None


def test_rate_limit_delays_second_request_to_same_host():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/a": FetchResult("https://example.com/a", 200, "a"),
        "https://example.com/b": FetchResult("https://example.com/b", 200, "b"),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(transport, clock=clock, min_request_interval=1.0)

    fetcher.fetch("https://example.com/a")
    # robots.txt then /a were both to example.com, back to back - the
    # second of those two should already have triggered one wait.
    assert len(clock.sleep_calls) == 1, clock.sleep_calls

    fetcher.fetch("https://example.com/b")
    # /b is a third request to the same host, still with no real time
    # having passed - must wait again.
    assert len(clock.sleep_calls) == 2, clock.sleep_calls


def test_rate_limit_does_not_leak_across_hosts():
    transport = FakeTransport({
        "https://a.com/robots.txt": FetchResult(
            "https://a.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://a.com/page": FetchResult("https://a.com/page", 200, "a"),
        "https://b.com/robots.txt": FetchResult(
            "https://b.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://b.com/page": FetchResult("https://b.com/page", 200, "b"),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(transport, clock=clock, min_request_interval=1.0)

    fetcher.fetch("https://a.com/page")
    calls_after_a = len(clock.sleep_calls)

    # b.com has never been requested before - its first-ever request must
    # not wait because a.com was just hit.
    fetcher.fetch("https://b.com/page")
    robots_and_page_for_b = 1  # b's own robots.txt -> b's own page, one wait
    assert len(clock.sleep_calls) == calls_after_a + robots_and_page_for_b, (
        clock.sleep_calls
    )


def test_rate_limit_no_wait_if_enough_time_already_passed():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/a": FetchResult("https://example.com/a", 200, "a"),
        "https://example.com/b": FetchResult("https://example.com/b", 200, "b"),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(transport, clock=clock, min_request_interval=1.0)

    fetcher.fetch("https://example.com/a")
    clock._now += 10.0  # plenty of real time passes between requests
    calls_before = len(clock.sleep_calls)

    fetcher.fetch("https://example.com/b")
    assert len(clock.sleep_calls) == calls_before, (
        "no wait should be needed - 10s already passed"
    )


def test_circuit_opens_after_threshold_consecutive_failures():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 503, "unavailable",
        ),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(
        transport, clock=clock, min_request_interval=0, failure_threshold=2,
    )

    for _ in range(2):
        try:
            fetcher.fetch("https://example.com/page")
            raise AssertionError("expected BotChallengeDetectedError")
        except BotChallengeDetectedError:
            pass

    calls_before = len(transport.calls)
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected CircuitOpenError")
    except CircuitOpenError:
        pass
    assert len(transport.calls) == calls_before, (
        "circuit-open must not call the transport at all"
    )


def test_circuit_stays_open_during_cooldown():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 503, "unavailable",
        ),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(
        transport, clock=clock, min_request_interval=0,
        failure_threshold=2, circuit_reset_timeout=30.0,
    )
    for _ in range(2):
        try:
            fetcher.fetch("https://example.com/page")
        except BotChallengeDetectedError:
            pass

    clock.sleep(10.0)  # well short of the 30s cooldown
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected CircuitOpenError")
    except CircuitOpenError:
        pass


def test_circuit_half_open_trial_success_closes_it():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": [
            FetchResult("https://example.com/page", 503, "unavailable"),
            FetchResult("https://example.com/page", 503, "unavailable"),
            FetchResult("https://example.com/page", 200, "recovered"),
        ],
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(
        transport, clock=clock, min_request_interval=0,
        failure_threshold=2, circuit_reset_timeout=30.0,
    )
    for _ in range(2):
        try:
            fetcher.fetch("https://example.com/page")
        except BotChallengeDetectedError:
            pass

    clock.sleep(31.0)  # cooldown elapsed - one trial request allowed
    result = fetcher.fetch("https://example.com/page")
    assert result.text == "recovered"

    # Circuit is fully closed now (success reset the failure count to 0).
    # Prove it takes a fresh full threshold of failures to reopen, not
    # just one - each of the next two failures should still reach the
    # transport (BotChallengeDetectedError, never CircuitOpenError), and
    # only the third attempt after that gets blocked.
    transport.responses["https://example.com/page"] = FetchResult(
        "https://example.com/page", 503, "unavailable",
    )
    for i in range(2):
        calls_before = len(transport.calls)
        try:
            fetcher.fetch("https://example.com/page")
            raise AssertionError("expected BotChallengeDetectedError")
        except CircuitOpenError:
            raise AssertionError(
                f"circuit reopened after only {i + 1} failure(s) post-reset "
                f"- threshold is 2"
            )
        except BotChallengeDetectedError:
            pass
        assert len(transport.calls) == calls_before + 1

    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected CircuitOpenError")
    except CircuitOpenError:
        pass


def test_circuit_half_open_trial_failure_reopens_and_extends_cooldown():
    transport = FakeTransport({
        "https://example.com/robots.txt": FetchResult(
            "https://example.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://example.com/page": FetchResult(
            "https://example.com/page", 503, "unavailable",
        ),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(
        transport, clock=clock, min_request_interval=0,
        failure_threshold=2, circuit_reset_timeout=30.0,
    )
    for _ in range(2):
        try:
            fetcher.fetch("https://example.com/page")
        except BotChallengeDetectedError:
            pass

    clock.sleep(31.0)  # cooldown elapsed - trial allowed, and it fails too
    try:
        fetcher.fetch("https://example.com/page")
    except BotChallengeDetectedError:
        pass

    # Immediately after the failed trial, circuit must be open again,
    # not reset to "give it another free trial" straight away.
    try:
        fetcher.fetch("https://example.com/page")
        raise AssertionError("expected CircuitOpenError")
    except CircuitOpenError:
        pass


def test_circuit_does_not_leak_across_hosts():
    transport = FakeTransport({
        "https://a.com/robots.txt": FetchResult(
            "https://a.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://a.com/page": FetchResult("https://a.com/page", 503, "down"),
        "https://b.com/robots.txt": FetchResult(
            "https://b.com/robots.txt", 200, "User-agent: *\nAllow: /\n",
        ),
        "https://b.com/page": FetchResult("https://b.com/page", 200, "fine"),
    })
    clock = FakeClock()
    fetcher = PoliteFetcher(
        transport, clock=clock, min_request_interval=0, failure_threshold=2,
    )
    for _ in range(2):
        try:
            fetcher.fetch("https://a.com/page")
        except BotChallengeDetectedError:
            pass
    try:
        fetcher.fetch("https://a.com/page")
        raise AssertionError("expected CircuitOpenError for a.com")
    except CircuitOpenError:
        pass

    # b.com must be entirely unaffected by a.com's open circuit.
    result = fetcher.fetch("https://b.com/page")
    assert result.text == "fine"


def test_cannot_disable_robots_check():
    transport = FakeTransport({})
    try:
        PoliteFetcher(transport, respect_robots_txt=False)
        raise AssertionError("expected TypeError - no such parameter exists")
    except TypeError:
        pass


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"\n{len(tests)} tests passed.")
