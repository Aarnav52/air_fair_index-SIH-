"""
Live demonstration of PoliteFetcher against real sites - the two confirmed
legal to scrape (Akasa Air, SpiceJet - see SIH26056_APIx_Research_and_
Plan_yug.md's Session Addendum), plus one confirmed-blocked site (IndiGo)
included on purpose to show the compliance layer correctly refusing
rather than evading.

This makes real network calls. Run from backend/: python -m app.scraper.demo_polite_fetcher_live
"""

import time

from app.scraper.polite_fetcher import (
    PoliteFetcher,
    RequestsTransport,
    RobotsDisallowedError,
    BotChallengeDetectedError,
    CircuitOpenError,
)

TARGETS = [
    ("Akasa Air", "https://www.akasaair.com/"),
    ("SpiceJet", "https://www.spicejet.com/"),
    ("IndiGo (expected to fail - network-level block)", "https://www.goindigo.in/"),
]


def run():
    fetcher = PoliteFetcher(RequestsTransport())
    print(f"{'Site':<55} {'Result':<20} {'Detail'}")
    print("-" * 100)

    for label, url in TARGETS:
        start = time.monotonic()
        try:
            result = fetcher.fetch(url)
            elapsed = time.monotonic() - start
            print(
                f"{label:<55} {'OK':<20} "
                f"HTTP {result.status_code}, {len(result.text)} bytes, {elapsed:.2f}s"
            )
        except RobotsDisallowedError as e:
            elapsed = time.monotonic() - start
            print(f"{label:<55} {'ROBOTS DISALLOWED':<20} {e} ({elapsed:.2f}s)")
        except BotChallengeDetectedError as e:
            elapsed = time.monotonic() - start
            print(f"{label:<55} {'BOT-CHALLENGE':<20} {e} ({elapsed:.2f}s)")
        except CircuitOpenError as e:
            elapsed = time.monotonic() - start
            print(f"{label:<55} {'CIRCUIT OPEN':<20} {e} ({elapsed:.2f}s)")
        except Exception as e:
            elapsed = time.monotonic() - start
            print(f"{label:<55} {'NETWORK ERROR':<20} {type(e).__name__}: {e} ({elapsed:.2f}s)")


if __name__ == "__main__":
    run()
