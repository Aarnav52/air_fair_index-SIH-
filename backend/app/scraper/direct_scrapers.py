"""
Generalized real-fare scrapers for Akasa Air and SpiceJet - any route, any
date, not hardcoded to DEL-BOM. Both go through PoliteFetcher.fetch() for
the compliance-gated initial navigation (robots.txt, rate limiting, the
circuit breaker), then continue the interactive search on that same
already-permitted page via PlaywrightTransport.last_page - same pattern
proven in the original scrape_akasa_live.py / scrape_spicejet_live.py.

Dropdown selection uses the IATA code (e.g. "DEL"), not city/airport name
text - the original one-route versions matched a specific airport's full
name ("Indira Gandhi International Airport"), which only worked for that
one city. The code is exact, unambiguous (avoids "Mumbai" also matching
"Navi Mumbai"), and is exactly what's already in the routes table - no
new lookup needed.
"""

import re
import json
import logging

from app.scraper.polite_fetcher import (
    PoliteFetcher,
    PlaywrightTransport,
    RobotsDisallowedError,
    BotChallengeDetectedError,
    CircuitOpenError,
)

logger = logging.getLogger(__name__)


class ScrapeBlocked(Exception):
    """Raised when PoliteFetcher's compliance layer refuses the fetch -
    the caller should treat this as "no data available", not retry."""


def _compliance_gated_navigate(fetcher, url):
    try:
        fetcher.fetch(url)
    except RobotsDisallowedError as e:
        raise ScrapeBlocked(f"robots.txt disallows {url}: {e}") from e
    except BotChallengeDetectedError as e:
        raise ScrapeBlocked(f"bot-challenge detected at {url}: {e}") from e
    except CircuitOpenError as e:
        raise ScrapeBlocked(f"circuit open for {url}: {e}") from e


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _pick_akasa_date(page, departure_date):
    """
    Akasa's date field is react-datepicker, a standard library - each day
    cell has an exact, deterministic aria-label ("Choose Wednesday,
    September 16th, 2026"), confirmed by inspection rather than guessed.
    Two months are shown at once by default, which covers T+1 and T+30
    from any day in a given month except very late in the month - the
    ">" next-month click is a fallback for that edge, not the common case.
    Missing entirely before this: the original single-route script never
    changed the date at all (it happened to only ever use today's
    default), which silently produced same-day (often "no flights
    found") results instead of the intended T+1/T+30 - found by actually
    checking the results screenshot, not assumed to have worked.
    """
    import datetime
    target = datetime.date.fromisoformat(departure_date)
    aria_label = f"Choose {target.strftime('%A')}, {target.strftime('%B')} {_ordinal(target.day)}, {target.year}"

    page.click('[name="DepartureDate"]')
    page.wait_for_timeout(800)
    selector = f'[aria-label="{aria_label}"]'
    for _ in range(3):
        if page.query_selector(selector):
            break
        page.click(".react-datepicker__navigation--next", timeout=3000)
        page.wait_for_timeout(500)
    page.click(selector, timeout=8000)
    page.wait_for_timeout(500)


def scrape_akasa(origin_code, origin_city, destination_code, destination_city, departure_date):
    """
    Akasa's autocomplete matches by city/airport NAME, not IATA code -
    typing the code directly produces no suggestions at all (found by
    testing). The dropdown item is also selected by exact city name, not
    the IATA-code badge next to it - the badge exists in the DOM (found
    by query_selector) but page.click() on it timed out on actionability
    (likely covered/not stable, the same class of issue as SpiceJet's
    overlay problem) even though a plain DOM query found it fine. City
    name is exact and unambiguous here too - Akasa lists "Mumbai" and
    "Navi Mumbai" as two distinct rows with different exact text, so
    there's no collision to worry about.

    departure_date: "YYYY-MM-DD". Returns a list of flight dicts, or []
    if the route/date genuinely has no results - never fabricated.
    """
    transport = PlaywrightTransport()
    fetcher = PoliteFetcher(transport)
    try:
        _compliance_gated_navigate(fetcher, "https://www.akasaair.com/flight-booking")
        page = transport.last_page
        page.wait_for_load_state("networkidle")

        page.click("#From")
        page.fill("#From", origin_city)
        page.wait_for_timeout(1200)
        page.click(f'text="{origin_city}"', timeout=8000)
        page.wait_for_timeout(500)

        page.click("#To")
        page.fill("#To", destination_city)
        page.wait_for_timeout(1200)
        page.click(f'text="{destination_city}"', timeout=8000)
        page.wait_for_timeout(500)

        try:
            page.click("text=Close", timeout=3000)
        except Exception:
            pass

        _pick_akasa_date(page, departure_date)

        page.click("text=Search Flights", force=True, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(4000)

        return _extract_akasa(page, departure_date, origin_code, destination_code)
    except ScrapeBlocked:
        raise
    except Exception as e:
        logger.warning(f"Akasa scrape failed for {origin_code}-{destination_code} on {departure_date}: {e}")
        return []
    finally:
        transport.close()


def _extract_akasa(page, departure_date, expected_origin, expected_destination):
    """
    stations regex matches any 3 uppercase letters, not a fixed airport
    whitelist (needed for genericity across arbitrary routes) - but that
    also matched unrelated text and produced two wrong-route rows in
    testing (one showing NMI - a nearby alternate airport Akasa lists as
    an option - and one showing a station that isn't even DEL). Both
    would have been real fabricated-route data if inserted. Fixed by
    requiring the row's stations to actually equal what was searched for,
    not just accepting whatever two codes appear first.
    """
    flights = []
    rows = page.query_selector_all("div.bg-background-highlight-orange.rounded-bl-lg")
    for row in rows:
        text = row.inner_text()
        flight_no = re.search(r"\b(QP\d{3,4})\b", text)
        stations = re.findall(r"\b([A-Z]{3})\b", text)
        duration = re.search(r"(\d+h \d+m)", text)
        price = re.search(r"₹\s?([\d,]+)", text)
        stops_match = re.search(r"(Non-stop|\d+ Stop)", text)

        h2s = row.query_selector_all("h2")
        current_times = []
        for h2 in h2s:
            cls = h2.get_attribute("class") or ""
            t = h2.inner_text().strip()
            if "line-through" not in cls and re.match(r"^\d{2}:\d{2}$", t):
                current_times.append(t)

        if not (flight_no and len(current_times) >= 2 and len(stations) >= 2 and price):
            continue
        if stations[0] != expected_origin or stations[1] != expected_destination:
            logger.warning(
                f"Skipping {flight_no.group(1)}: extracted route "
                f"{stations[0]}-{stations[1]} != requested "
                f"{expected_origin}-{expected_destination}"
            )
            continue
        flights.append({
            "airline_name": "Akasa Air",
            "flight_number": flight_no.group(1),
            "origin": stations[0],
            "destination": stations[1],
            "departure_date": departure_date,
            "departure_time": current_times[0],
            "arrival_time": current_times[1],
            "duration": duration.group(1) if duration else None,
            "stops_text": stops_match.group(1) if stops_match else None,
            "raw_price_displayed": int(price.group(1).replace(",", "")),
        })
    return flights


def scrape_spicejet(origin_code, destination_code, departure_date):
    """
    departure_date: "YYYY-MM-DD". Returns a list of flight dicts, or []
    if the route/date genuinely has no results - never fabricated.
    """
    transport = PlaywrightTransport()
    fetcher = PoliteFetcher(transport)
    try:
        _compliance_gated_navigate(fetcher, "https://www.spicejet.com/")
        page = transport.last_page
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # From/To are custom widgets with no name/placeholder/testid
        # (React Native Web) - position click confirmed against a
        # screenshot, same as the original single-route version.
        page.mouse.click(160, 265)
        page.wait_for_timeout(1200)
        page.click(f'text="{origin_code}"', timeout=8000)
        page.wait_for_timeout(500)

        page.mouse.click(410, 265)
        page.wait_for_timeout(1200)
        page.click(f'text="{destination_code}"', timeout=8000)
        page.wait_for_timeout(1000)

        _pick_spicejet_date(page, departure_date)

        page.click("text=Search Flight", force=True, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.wait_for_timeout(3000)

        return _extract_spicejet(page, departure_date)
    except ScrapeBlocked:
        raise
    except Exception as e:
        logger.warning(f"SpiceJet scrape failed for {origin_code}-{destination_code} on {departure_date}: {e}")
        return []
    finally:
        transport.close()


def _pick_spicejet_date(page, departure_date):
    """
    SpiceJet's calendar shows 3 months at once with plain day-number text
    and no aria-label to disambiguate - a bare `text="15"` click matches
    14 elements across all visible months and Playwright refuses it
    (strict-mode violation: ambiguous locator).

    The original version wrapped that click in try/except: pass, which
    silently swallowed the error and picked no date at all, leaving
    whatever date happened to be already selected - a real bug, found by
    noticing 0 rows came back for a T+30 date where flights should exist,
    not assumed to be a genuine "no flights" result.

    Fixed by scoping the search to a specific month: walk up from the
    month-name header ("October 2026") until exactly one exact-text
    match for the day number exists among that ancestor's descendants
    (empirically level 2 - confirmed by counting matches at each level
    before picking one, not guessed).
    """
    import datetime
    target = datetime.date.fromisoformat(departure_date)
    month_label = f"{target.strftime('%B')} {target.year}"
    day_str = str(target.day)

    header = page.query_selector(f'text="{month_label}"')
    if header is None:
        logger.warning(f"SpiceJet date picker: month '{month_label}' not visible, leaving default date")
        return

    cell = header.evaluate_handle(
        """(node, day) => {
            let el = node;
            for (let levels = 0; levels < 6; levels++) {
                const matches = [];
                for (const n of el.querySelectorAll('*')) {
                    if (n.children.length === 0 && n.textContent.trim() === day) matches.push(n);
                }
                if (matches.length === 1) return matches[0];
                if (el.parentElement) el = el.parentElement;
            }
            return null;
        }""",
        day_str,
    )
    if cell is None or cell.as_element() is None:
        logger.warning(f"SpiceJet date picker: could not uniquely locate day {day_str} in {month_label}")
        return
    cell.as_element().click()
    page.wait_for_timeout(500)


def _extract_spicejet(page, departure_date):
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
            "airline_name": "SpiceJet",
            "flight_number": flight_no.replace(" ", ""),
            "departure_date": departure_date,
            "departure_time": times[0],
            "arrival_time": times[1],
            "duration": duration.group(1) if duration else None,
            "raw_price_displayed": int(price.group(1).replace(",", "")),
        })
    return flights


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    origin_code, origin_city, dest_code, dest_city, date = sys.argv[1:6]
    print("Akasa:", json.dumps(scrape_akasa(origin_code, origin_city, dest_code, dest_city, date), indent=2))
    print("SpiceJet:", json.dumps(scrape_spicejet(origin_code, dest_code, date), indent=2))
