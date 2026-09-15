"""
Automation entrypoint: runs every scraper (SerpApi + the two compliant
direct-airline scrapers) across every active route in the DB, for T+1
and T+30 - the two booking windows this project has scoped to for now.

Not on a schedule yet (no cron/Airflow wired up) - this is the single
command that does a full sweep when run, the piece a scheduler would
call. Run: python -m app.scraper.run_all_scrapers
"""

import logging
import datetime

import pytz

from app.db.connection import get_db_connection
from app.db.queries import get_or_create_source, insert_observations
from app.services.scraping_service import scraping_service
from app.scraper.direct_scrapers import scrape_akasa, scrape_spicejet, ScrapeBlocked

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")
WINDOWS = {
    "T+1": 1,
    "T+30": 30,
}


def get_active_routes(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT route_id, origin_airport, destination_airport,
                   origin_city, destination_city
            FROM routes WHERE is_active = true ORDER BY route_id
        """)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def direct_flight_to_observation(flight, route_id, window, departure_date, scrape_timestamp):
    return {
        "airline_name": flight["airline_name"],
        "flight_number": flight["flight_number"],
        "scrape_timestamp": scrape_timestamp,
        "departure_date": departure_date,
        "departure_time": flight["departure_time"],
        "advance_booking_window": window,
        "cabin_class": "economy",
        "fare_family": flight.get("fare_family"),
        "stops": 0 if (flight.get("stops_text") or "Non-stop") == "Non-stop" else 1,
        "seat_availability_hint": None,
        "raw_price_displayed": flight["raw_price_displayed"],
        "base_fare": None,
        "fuel_surcharge": None,
        "taxes_fees": None,
        "gst_amount": None,
        "convenience_fee": None,
        "currency": "INR",
        "scrape_status": "observed",
        "data_provenance": "real_scraped",
        "raw_payload_snapshot": __import__("json").dumps(flight),
    }


def _store_flights(conn, flights, source_name, route, window, target_date):
    if not flights:
        return 0
    source_id = get_or_create_source(conn, source_name, "airline_direct")
    # One timestamp for every observation in this scrape, matching the SerpApi path.
    scrape_timestamp = datetime.datetime.now(IST).isoformat()
    observations = [
        direct_flight_to_observation(f, route["route_id"], window, target_date, scrape_timestamp)
        for f in flights
    ]
    return insert_observations(conn, observations, route["route_id"], source_id)


def run_akasa(conn, route, window, target_date):
    try:
        flights = scrape_akasa(
            route["origin_airport"].strip(), route["origin_city"],
            route["destination_airport"].strip(), route["destination_city"],
            target_date,
        )
    except ScrapeBlocked as e:
        logger.info(f"Akasa blocked for route {route['route_id']} ({window}): {e}")
        return 0
    return _store_flights(conn, flights, "Akasa Air Direct", route, window, target_date)


def run_spicejet(conn, route, window, target_date):
    try:
        flights = scrape_spicejet(
            route["origin_airport"].strip(), route["destination_airport"].strip(), target_date,
        )
    except ScrapeBlocked as e:
        logger.info(f"SpiceJet blocked for route {route['route_id']} ({window}): {e}")
        return 0
    return _store_flights(conn, flights, "SpiceJet Direct", route, window, target_date)


def run_full_sweep(route_limit=None, windows=None):
    """
    windows: subset of WINDOWS keys to sweep (e.g. ["T+1"]). None/omitted
    means all of them - kept so a scheduler can run T+1 and T+30 on
    independent cadences (T+1 changes fast, T+30 barely moves day to day)
    without hitting SerpApi/the direct scrapers for windows nobody asked for.
    """
    active_windows = {w: WINDOWS[w] for w in windows} if windows else WINDOWS

    today = datetime.datetime.now(IST).date()
    summary = {"serpapi": 0, "akasa": 0, "spicejet": 0, "errors": []}

    with get_db_connection() as conn:
        routes = get_active_routes(conn)
        if route_limit is not None:
            routes = routes[:route_limit]

        for route in routes:
            origin, dest = route["origin_airport"].strip(), route["destination_airport"].strip()
            logger.info(f"=== Route {origin}-{dest} (route_id={route['route_id']}) ===")

            try:
                result = scraping_service.run_scrape(origin, dest, list(active_windows.keys()))
                inserted = sum(w.get("rows_inserted", 0) for w in result["details"])
                summary["serpapi"] += inserted
                logger.info(f"SerpApi: {inserted} rows inserted")
            except Exception as e:
                logger.error(f"SerpApi failed for {origin}-{dest}: {e}")
                summary["errors"].append(f"serpapi/{origin}-{dest}: {e}")

            for window, days_ahead in active_windows.items():
                target_date = (today + datetime.timedelta(days=days_ahead)).isoformat()

                try:
                    n = run_akasa(conn, route, window, target_date)
                    summary["akasa"] += n
                    logger.info(f"Akasa {window} ({target_date}): {n} rows inserted")
                except Exception as e:
                    logger.error(f"Akasa failed for {origin}-{dest} {window}: {e}")
                    summary["errors"].append(f"akasa/{origin}-{dest}/{window}: {e}")

                try:
                    n = run_spicejet(conn, route, window, target_date)
                    summary["spicejet"] += n
                    logger.info(f"SpiceJet {window} ({target_date}): {n} rows inserted")
                except Exception as e:
                    logger.error(f"SpiceJet failed for {origin}-{dest} {window}: {e}")
                    summary["errors"].append(f"spicejet/{origin}-{dest}/{window}: {e}")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sweep active routes for real fares.")
    parser.add_argument(
        "--window", action="append", choices=list(WINDOWS.keys()), dest="windows",
        help="Booking window to sweep (repeatable). Omit to sweep all windows.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only sweep the first N active routes (for testing).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = run_full_sweep(route_limit=args.limit, windows=args.windows)
    print("\n=== SWEEP SUMMARY ===")
    print(f"Windows:                 {args.windows or list(WINDOWS.keys())}")
    print(f"SerpApi rows inserted:   {result['serpapi']}")
    print(f"Akasa rows inserted:     {result['akasa']}")
    print(f"SpiceJet rows inserted:  {result['spicejet']}")
    if result["errors"]:
        print(f"\n{len(result['errors'])} errors:")
        for e in result["errors"]:
            print(f"  - {e}")
