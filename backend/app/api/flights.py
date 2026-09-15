from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from app.db.connection import get_db_connection
from app.services.scraping_service import scraping_service

router = APIRouter()

class ScrapeRequest(BaseModel):
    origin: str
    destination: str
    windows: List[str]

@router.get("/")
def get_flights(
    route: Optional[str] = Query(None, description="e.g. DEL-BOM"),
    window: Optional[str] = Query(None, description="e.g. T+1")
):
    """
    Fetch flights from the database with optional filtering.
    """
    query = """
        SELECT f.observation_id, f.airline_name, f.flight_number, f.departure_date, 
               f.departure_time, f.scrape_timestamp,f.raw_price_displayed, f.advance_booking_window,
               r.origin_airport, r.destination_airport
        FROM flight_observations f
        JOIN routes r ON f.route_id = r.route_id
        WHERE 1=1
    """
    params = []

    if route:
        parts = route.split("-")
        if len(parts) == 2:
            query += " AND r.origin_airport = %s AND r.destination_airport = %s"
            params.extend([parts[0], parts[1]])

    if window:
        query += " AND f.advance_booking_window = %s"
        params.append(window)
        
    query += " ORDER BY f.departure_date ASC, f.raw_price_displayed ASC LIMIT 1000"

    results = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                for row in rows:
                    results.append({
                        "observation_id": row[0],
                        "airline_name": row[1],
                        "flight_number": row[2],
                        "departure_date": row[3],
                        "departure_time": str(row[4]) if row[4] else None,
                        "scrape_timestamp": row[5].isoformat() if row[5] else None,
                        "price": float(row[6]) if row[6] else None,
                        "window": row[7],
                        "origin": row[8],
                        "destination": row[9]
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return results

@router.post("/scrape")
def trigger_scrape(req: ScrapeRequest):
    """
    Triggers the scraping service.
    """
    if not req.windows:
        raise HTTPException(status_code=400, detail="Must provide at least one window")
        
    try:
        result = scraping_service.run_scrape(req.origin, req.destination, req.windows)
        
        # If the overall status is failed, we can still return 200 with failure details 
        # or 500 depending on preference. We'll return 200 with details for visibility.
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
