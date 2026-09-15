from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.db.connection import get_db_connection

router = APIRouter()

WINDOWS = ["T+1", "T+7", "T+15", "T+30", "T+45"]


def _resolve_route_id(cursor, route: str):
    parts = route.split("-")
    if len(parts) != 2:
        return None, f"Invalid route format: {route}. Expected e.g. DEL-BOM"
    origin, destination = parts[0], parts[1]
    cursor.execute(
        "SELECT route_id FROM routes WHERE origin_airport = %s AND destination_airport = %s",
        (origin, destination),
    )
    row = cursor.fetchone()
    if not row:
        return None, f"Route {route} not found in database"
    return row[0], None


def _fetch_index_series(cursor, route_id: int, window: str) -> dict:
    """
    Real elementary Jevons index series for one route+window, read from
    `index_values` (populated by jevons_engine_cloud.py — the validated
    engine, not a placeholder). avg_price is computed separately from
    flight_observations for display purposes only; index_value is the
    real geometric-mean-of-price-relatives figure.
    """
    cursor.execute(
        """
        SELECT observation_date, base_period_date, index_value, num_observations_used
        FROM index_values
        WHERE index_type = 'elementary' AND route_id = %s AND advance_booking_window = %s
        ORDER BY observation_date ASC
        """,
        (str(route_id), window),
    )
    rows = cursor.fetchall()

    if not rows:
        return {
            "route": None,
            "window": window,
            "base_date": None,
            "base_avg_price": None,
            "series": [],
            "message": "No index data available for this route/window combination yet.",
        }

    dates = [r[0] for r in rows]
    base_period_date = rows[0][1]

    cursor.execute(
        """
        SELECT DATE(scrape_timestamp AT TIME ZONE 'Asia/Kolkata') AS scrape_date,
               AVG(raw_price_displayed) AS avg_price
        FROM flight_observations
        WHERE route_id = %s AND advance_booking_window = %s
          AND scrape_status = 'observed' AND raw_price_displayed IS NOT NULL
          AND DATE(scrape_timestamp AT TIME ZONE 'Asia/Kolkata') = ANY(%s::date[])
        GROUP BY scrape_date
        """,
        (route_id, window, dates),
    )
    avg_price_by_date = {r[0]: float(r[1]) for r in cursor.fetchall()}

    series = [
        {
            "date": str(observation_date),
            "avg_price": round(avg_price_by_date[observation_date], 2) if observation_date in avg_price_by_date else None,
            "index_value": float(index_value),
            "num_observations_used": num_observations_used,
        }
        for observation_date, _base_period_date, index_value, num_observations_used in rows
    ]

    return {
        "window": window,
        "base_date": str(base_period_date),
        "base_avg_price": avg_price_by_date.get(base_period_date),
        "series": series,
    }


@router.get("/")
def get_index(
    route: str = Query(..., description="Route code e.g. DEL-BOM"),
    window: str = Query(..., description="Booking window: T+1, T+7, T+15, T+30 or T+45"),
):
    """
    Returns the real elementary Jevons Price Index series for a route and
    booking window, computed by jevons_engine_cloud.py and read from
    `index_values`.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            route_id, error = _resolve_route_id(cursor, route)
            if error:
                raise HTTPException(status_code=400, detail=error)
            result = _fetch_index_series(cursor, route_id, window)

    result["route"] = route
    return result


@router.get("/summary")
def get_index_summary(
    route: str = Query(..., description="Route code e.g. DEL-BOM"),
):
    """
    Returns the real Jevons index for every booking window in one call.
    Useful for dashboard summary cards.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            route_id, error = _resolve_route_id(cursor, route)
            if error:
                raise HTTPException(status_code=400, detail=error)
            results = {}
            for window in WINDOWS:
                series_result = _fetch_index_series(cursor, route_id, window)
                series_result["route"] = route
                results[window] = series_result

    return {"route": route, "index": results}
