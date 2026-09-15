# Airfare Price Index Backend (SIH Prototype)

## Stack
- **Python 3.14** · FastAPI · Uvicorn
- **PostgreSQL** (Supabase)
- **SerpApi** – Google Flights engine
- **Vite + React** frontend (separate)

---

## Project Structure
```
backend/
├── .env                          ← credentials (never commit)
├── requirements.txt
├── run_sweep_t1.bat              ← Task Scheduler entrypoint, T+1 (every 6h)
├── run_sweep_t30.bat             ← Task Scheduler entrypoint, T+30 (daily)
├── logs/                         ← sweep logs (gitignored)
├── test_polite_fetcher.py        ← 25 unit tests, fake transport, no real network
├── scripts/
│   └── check_db.py               ← manual schema/data inspector (standalone, no app import)
└── app/
    ├── config.py                 ← loads .env
    ├── main.py                   ← FastAPI app + CORS, mounts routers below
    ├── db/
    │   ├── connection.py         ← psycopg2 context manager
    │   └── queries.py            ← INSERT with same-day dedup guard +
    │                                fee-decomposition hook
    ├── scraper/
    │   ├── polite_fetcher.py     ← compliance gate every scraper goes through
    │   │                            (robots.txt, bot-challenge detection,
    │   │                            per-host rate limit, circuit breaker)
    │   ├── serpapi_client.py     ← SerpApi Google Flights client
    │   ├── flight_parser.py      ← SerpApi JSON → DB dict parser
    │   ├── direct_scrapers.py    ← Akasa Air / SpiceJet, routed through
    │   │                            PoliteFetcher, any route/date
    │   ├── run_all_scrapers.py   ← full-sweep entrypoint (--window T+1/T+30,
    │   │                            --limit N); what the .bat files call
    │   └── scrape_akasa_live.py, scrape_spicejet_live.py,
    │       demo_polite_fetcher_live.py
    │                            ← original single-route demo scripts,
    │                               superseded by direct_scrapers.py +
    │                               run_all_scrapers.py but kept as minimal
    │                               standalone examples of the pattern
    ├── services/
    │   ├── scraping_service.py   ← orchestrates the SerpApi T+1/T+30 scrape
    │   ├── fee_decomposition.py  ← tariff-schedule-derived base_fare/
    │   │                            taxes_fees/udf/gst_amount/fuel_surcharge
    │   └── index_service.py      ← ⚠ SEE "Jevons Index" SECTION BELOW —
    │                                this is a placeholder, not the real engine
    └── api/
        ├── flights.py             ← GET /flights/  POST /flights/scrape
        ├── routes.py              ← GET /routes/
        └── index.py               ← GET /index/  GET /index/summary
                                       (currently backed by the placeholder
                                       above, not jevons_engine/)
```

The real statistics engine, `jevons_engine/jevons_engine_cloud.py`, lives at
the repo root (sibling of `backend/`, not inside it) — it's owned/maintained
separately and is not yet wired to the API above (see below).

---

## Environment Variables

Create `backend/.env`:
```env
DATABASE_URL=postgresql://...   # Supabase connection string
SERPAPI_KEY=...                 # SerpApi API key
```

Create `frontend/.env`:
```env
VITE_API_URL=http://localhost:8000
```

---

## How to Run

### 1 — Backend

```bash
cd backend
pip3 install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend is live at: http://localhost:8000
Swagger docs at:    http://localhost:8000/docs

### 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend is live at: http://localhost:5173

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health check |
| GET | `/routes/` | All active routes |
| GET | `/flights/` | Stored observations (filter: `?route=DEL-BOM&window=T+1`) |
| POST | `/flights/scrape` | Trigger scrape `{"origin":"DEL","destination":"BOM","windows":["T+1","T+30"]}` |
| GET | `/index/` | Jevons index series (`?route=DEL-BOM&window=T+1`) |
| GET | `/index/summary` | Index for all windows (`?route=DEL-BOM`) |

---

## Data Flow

Two collection paths, one shared write path (see `SIH26056_APIx_
Architecture_and_Pipelines.md` one level above the repo for full diagrams):

```
Windows Task Scheduler (run_sweep_t1.bat / run_sweep_t30.bat)
        ↓
  run_all_scrapers.py  (run_full_sweep — every active route)
        ├──→ scraping_service.py → serpapi_client.py → flight_parser.py
        └──→ direct_scrapers.py → polite_fetcher.py → Akasa/SpiceJet sites
        ↓                                   (both paths converge here)
  queries.py:
    1. same-IST-day dedup check (skip already-scraped flight+date+window)
    2. fee_decomposition.py (fill base_fare/taxes/udf/gst if a tariff
       schedule exists for this airline+station — never fabricated)
    3. INSERT INTO flight_observations
        ↓
  Supabase PostgreSQL (apix(SIH))
        ↓
  FastAPI endpoints  (serve to frontend)
        ↓
  LiveDataPanel.jsx / Dashboard.jsx / AirlineAnalytics.jsx
```

---

## Jevons Index

**⚠ `index_service.py` is a placeholder, not the real Jevons/GEKS-Jevons
engine.** Despite its name and docstring, `calculate_jevons_index()` does
NOT compute a geometric mean of price relatives — it computes
`(AVG(price today) / AVG(price on base date)) × 100`, a simple ratio of
arithmetic means. (It even defines an unused `_geometric_mean()` helper
that nothing calls — dead code, not wired in.) This is what `GET /index/`
currently returns, and what the dashboard's "APEX-IND GEKS" panel displays.

The real, correctly-implemented engine is `jevons_engine/
jevons_engine_cloud.py` (repo root, not under `backend/`) — it genuinely
computes `exp(mean(log(price_relative))) * 100` per the Jevons formula,
with a route-level and national rollup on top. It reads from
`cleaned_observations_table` and writes to an `index_values` table. **It is
not yet wired to `GET /index/`** — that reconnection (fix the table schema
so the engine's own output actually persists, point this API at it instead
of `index_service.py`) is a known, open, in-progress item, not a
methodology gap. Don't present the current `/index/` output as GEKS-Jevons
without this caveat.

---

## Notes

- `lead_time_days` is a **PostgreSQL generated column** — Python never writes it
- `cabin_class` must be one of: `economy`, `premium_economy`, `business`
- `source_type` must be one of: `airline_direct`, `ota`, `api`
- Duplicate guard is two-layered: a DB unique constraint
  (`ON CONFLICT (route_id, source_id, flight_number, departure_date,
  scrape_timestamp) DO NOTHING`) plus an application-level same-IST-day
  check in `insert_observations()` — the DB constraint alone can't catch
  two sweep runs minutes apart, since `scrape_timestamp` is fresh every
  call; the app-level check is what actually prevents that.
- All timestamps use `Asia/Kolkata` timezone

---

## Adding More Routes Later

In `scraping_service.py`, add entries to `city_lookup`:
```python
self.city_lookup = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",   # add more here
    "CCU": "Kolkata",
}
```
Then POST to `/flights/scrape` with the new route.
