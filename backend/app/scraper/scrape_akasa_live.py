"""
Live extraction demo: real flight fare data from Akasa Air's own site.

The initial navigation goes through PoliteFetcher.fetch() with
PlaywrightTransport - so robots.txt, per-host rate limiting, and the
circuit breaker all genuinely apply before any interactive scraping
happens, exactly like every other fetch in this project. Only the
search-form interaction (fill/click/wait, which isn't a "fetch a new
URL" operation PoliteFetcher's interface models) continues directly on
that same, already-permitted page via transport.last_page.

Run from backend/: python -m app.scraper.scrape_akasa_live
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

BOOKING_URL = "https://www.akasaair.com/flight-booking"
FLIGHT_ROW_SELECTOR = "div.bg-background-highlight-orange.rounded-bl-lg"


def extract_flights(page):
    """
    Times come from the row's h2 elements specifically, not a blind regex
    over the row's full text - a schedule-revised flight shows BOTH its
    current time and its original time (struck through, class contains
    "line-through"), and a naive "last time in the text" regex silently
    picks the stale, struck-through one instead of the real current time.
    Caught by comparing extracted output against a screenshot of the same
    page, not assumed correct.
    """
    flights = []
    rows = page.query_selector_all(FLIGHT_ROW_SELECTOR)
    for row in rows:
        text = row.inner_text()
        flight_no = re.search(r"\b(QP\d{3,4})\b", text)
        stations = re.findall(r"\b(DEL|BOM|BLR|HYD|CCU|MAA|AMD)\b", text)
        duration = re.search(r"(\d+h \d+m)", text)
        price = re.search(r"₹\s?([\d,]+)", text)
        stops = "Non-stop" if "Non-stop" in text else (
            re.search(r"(\d+ Stop)", text).group(1) if re.search(r"(\d+ Stop)", text) else None
        )

        h2s = row.query_selector_all("h2")
        current_times = []
        for h2 in h2s:
            cls = h2.get_attribute("class") or ""
            t = h2.inner_text().strip()
            if "line-through" not in cls and re.match(r"^\d{2}:\d{2}$", t):
                current_times.append(t)

        if not (flight_no and len(current_times) >= 2 and len(stations) >= 2 and price):
            continue  # not a real flight row - skip rather than guess

        flights.append({
            "flight_number": flight_no.group(1),
            "origin": stations[0],
            "destination": stations[1],
            "departure_time": current_times[0],
            "arrival_time": current_times[1],
            "duration": duration.group(1) if duration else None,
            "stops": stops,
            "price_inr": int(price.group(1).replace(",", "")),
        })
    return flights


def run():
    transport = PlaywrightTransport()
    fetcher = PoliteFetcher(transport)

    try:
        # Compliance-gated: robots.txt, rate limit, circuit breaker all
        # apply to this exact URL before anything else happens.
        fetcher.fetch(BOOKING_URL)
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

    # Compliance check passed - continue on that SAME permitted page.
    # PlaywrightTransport.get() only waits for "load", not full JS
    # hydration - this SPA's search button stays disabled until its own
    # JS finishes initializing, so wait for that before interacting.
    page = transport.last_page
    page.wait_for_load_state("networkidle")
    page.click("#From")
    page.fill("#From", "Delhi")
    page.wait_for_timeout(1200)
    page.click("text=Indira Gandhi International Airport")
    page.wait_for_timeout(500)
    page.click("#To")
    page.fill("#To", "Mumbai")
    page.wait_for_timeout(1200)
    page.click("text=Chhatrapati Shivaji Maharaj International Airport")
    page.wait_for_timeout(500)
    try:
        page.click("text=Close", timeout=3000)
    except Exception:
        pass
    page.click("text=Search Flights")
    page.wait_for_timeout(6000)

    flights = extract_flights(page)
    transport.close()
    return flights


if __name__ == "__main__":
    flights = run()
    print(json.dumps(flights, indent=2))
    print(f"\n{len(flights)} real flights extracted from a live, compliance-gated Akasa Air search (DEL -> BOM).")
