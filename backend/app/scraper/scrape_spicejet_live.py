"""
Live extraction demo: real flight fare data from SpiceJet's own site.

Same pattern as scrape_akasa_live.py: the initial navigation goes through
PoliteFetcher.fetch() with PlaywrightTransport (robots.txt, rate limiting,
circuit breaker all genuinely apply), then the interactive search
continues on that same, already-permitted page via transport.last_page.

SpiceJet's booking widget is built with React Native Web (not a plain
HTML form like Akasa's) - inputs lack normal name/placeholder attributes
and some elements needed a position click / force click rather than
text-based selectors. Noted inline where that's why.

Run from backend/: python -m app.scraper.scrape_spicejet_live
"""

import re
import json

from app.scraper.polite_fetcher import (
    PoliteFetcher,
    PlaywrightTransport,
    RobotsDisallowedError,
    BotChallengeDetectedError,
    CircuitOpenError,
)

HOME_URL = "https://www.spicejet.com/"


def extract_flights(page):
    """
    #aircraft-no is the one stable id SpiceJet's markup gives us (found by
    inspection - React Native Web output otherwise has no semantic
    classes). Its own row div doesn't include the fare-tier prices
    (a separate sibling section), so we walk UP one level at a time and
    stop at the smallest ancestor whose text contains a price.

    A fixed walk distance was tried first and was wrong: both rows
    landed on the same shared results-list container once far enough up,
    so every row silently returned the FIRST row's price and times.
    Caught by comparing extracted output against the screenshot, where
    the two rows clearly have different flights/prices - not assumed
    correct just because it ran without error.
    """
    flights = []
    flight_no_els = page.query_selector_all("#aircraft-no")
    for el in flight_no_els:
        flight_no = el.inner_text().strip()
        container_text = page.evaluate(
            """(node) => {
                let el = node;
                for (let i = 0; i < 20; i++) {
                    if (!el.parentElement) break;
                    el = el.parentElement;
                    if (el.innerText && el.innerText.includes('₹')) break;
                }
                return el.innerText;
            }""",
            el,
        )
        times = re.findall(r"\b(\d{1,2}:\d{2})\b", container_text)
        price = re.search(r"₹\s?([\d,]+)", container_text)
        duration = re.search(r"(\d+h \d+m)", container_text)
        if not (flight_no and len(times) >= 2 and price):
            continue
        flights.append({
            "flight_number": flight_no,
            "departure_time": times[0],
            "arrival_time": times[1],
            "duration": duration.group(1) if duration else None,
            "price_inr": int(price.group(1).replace(",", "")),
        })
    return flights


def run():
    transport = PlaywrightTransport()
    fetcher = PoliteFetcher(transport)

    try:
        fetcher.fetch(HOME_URL)
    except RobotsDisallowedError:
        print("BLOCKED: robots.txt disallows this URL - not proceeding.")
        transport.close()
        return []
    except BotChallengeDetectedError:
        print("BLOCKED: bot-challenge detected - not proceeding.")
        transport.close()
        return []
    except CircuitOpenError:
        print("BLOCKED: circuit open for this host - not proceeding.")
        transport.close()
        return []

    page = transport.last_page
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # "From" already defaults to Delhi (DEL) on load. Click "To" - React
    # Native Web renders its placeholder as non-queryable content, so a
    # position click (confirmed against a screenshot) is used instead of
    # a text/attribute selector.
    page.mouse.click(410, 265)
    page.wait_for_timeout(1500)
    page.click("text=Mumbai", timeout=10000)
    page.wait_for_timeout(1000)

    # A date picker auto-opens after selecting the destination, already
    # defaulted to a valid date - just confirm it.
    try:
        page.click('text="22"', timeout=5000)
        page.wait_for_timeout(500)
    except Exception:
        pass

    # The button itself is a real, visible, intended target - force=True
    # bypasses a stray overlay element intercepting the click, it is not
    # evading anything about the site's own behavior.
    page.click("text=Search Flight", force=True, timeout=15000)
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    page.screenshot(path="spicejet_final_results.png")

    flights = extract_flights(page)
    transport.close()
    return flights


if __name__ == "__main__":
    flights = run()
    print(json.dumps(flights, indent=2))
    print(f"\n{len(flights)} real flights extracted from a live, compliance-gated SpiceJet search (DEL -> BOM).")
