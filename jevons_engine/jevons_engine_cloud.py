"""
=============================================================================
APIx Jevons Index Calculation Engine (Cloud Version)
Student ID: 25BCE355
Script: jevons_engine_cloud.py
Description: Fetches cleaned flight observation records from Supabase,
             computes elementary Jevons price indices for matched airline
             products, rolls them up to Route-level and National APIx levels,
             and pushes the calculated index records into the 'index_values'
             Supabase table.

Scope: STRICTLY Jevons only — Elementary → Route → National.
       No GEKS, Laspeyres, Fisher, Dutot, Carli, or any other methodology.

Indexed price variable: clean_base_fare (pre-tax base fare).
Outlier detection (upstream): operated on raw_price_displayed — intentional.

Weighting note: booking-window weights (WINDOW_WEIGHTS) are an estimated
assumption (no proprietary booking-lead-time data exists) - keep exactly as
designed by the stats team. Route weights are NOT an assumption - real DGCA
monthly passenger-volume data already exists in the `routes` table, so
route weighting is loaded from there via `_load_dgca_route_weights()`
instead of a hardcoded guess. A route with no DGCA figure on file falls
back to weight 1.0 (unweighted) rather than a fabricated number.
=============================================================================
"""

import os
import sys
import json
import logging
from typing import TYPE_CHECKING, List, Dict, Any, Optional

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv

if TYPE_CHECKING:
    from supabase import Client as SupabaseClient  # pyright: ignore[reportMissingImports]
else:
    SupabaseClient = Any

# Try importing Supabase client
try:
    from supabase import create_client  # pyright: ignore[reportMissingImports]
except ImportError:
    create_client = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("JevonsEngineCloud")


# ---------------------------------------------------------------------------
# Weighting Matrices & Calibration
# ---------------------------------------------------------------------------

# Advance Booking Window Weights. This is an ESTIMATE, not fitted to real
# booking data (no proprietary airline purchase data is available) - a
# right-skewed approximation per the Ayoubkhani & Thomas (ONS, 2022)
# approach. Publish as an assumption, never as settled fact.
WINDOW_WEIGHTS: Dict[str, float] = {
    "T+1": 0.12,   # Urgent / Close-in (12%)
    "T+7": 0.28,   # Short horizon (28%)
    "T+15": 0.22,  # Medium horizon (22%)
    "T+30": 0.20,  # Advance planning (20%)
    "T+45": 0.18,  # Long horizon (18%)
}


# ---------------------------------------------------------------------------
# Real DGCA route-traffic weighting (loaded from the DB, not hardcoded)
# ---------------------------------------------------------------------------

def _load_dgca_route_weights() -> Dict[str, float]:
    """
    Loads real DGCA monthly passenger-volume figures from the `routes`
    table and normalizes them into weights that sum to 1 across routes
    that have a figure on file. Routes with no DGCA figure are simply
    absent from the returned dict - callers should fall back to an
    unweighted default (1.0) for those, never a guessed number.
    """
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        logger.warning(
            "DATABASE_URL not set; cannot load real DGCA route weights. "
            "National rollup will be unweighted for every route."
        )
        return {}

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT route_id, dgca_monthly_passenger_volume
                FROM routes
                WHERE dgca_monthly_passenger_volume IS NOT NULL
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        logger.warning("No routes have a DGCA passenger-volume figure on file.")
        return {}

    total_volume = sum(volume for _route_id, volume in rows)
    if total_volume <= 0:
        return {}

    weights = {str(route_id): volume / total_volume for route_id, volume in rows}
    logger.info(
        f"Loaded real DGCA route weights for {len(weights)} route(s) "
        f"(total monthly passenger volume: {total_volume:,})."
    )
    return weights


# ---------------------------------------------------------------------------
# Supabase client (reads only — writes go through psycopg2/DATABASE_URL,
# see push_to_supabase below, since index_values' INSERT policy is
# service_role-only and this project doesn't otherwise use a service_role
# credential anywhere).
# ---------------------------------------------------------------------------

def get_supabase_client() -> SupabaseClient:
    """
    Initializes and returns the Supabase client using environment variables.
    Reads SUPABASE_URL and SUPABASE_KEY from environment or .env file.
    """
    load_dotenv()

    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing Supabase credentials! Please set SUPABASE_URL and SUPABASE_KEY "
            "in your environment variables or in a .env file."
        )

    # Sanitize base URL by stripping trailing slashes or /rest/v1
    supabase_url = supabase_url.rstrip("/")
    if supabase_url.endswith("/rest/v1"):
        supabase_url = supabase_url[:-8].rstrip("/")

    if create_client is None:
        raise ImportError(
            "The 'supabase' package is not installed. Please run: pip install supabase"
        )

    logger.info("Initializing Supabase client...")
    client: SupabaseClient = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized successfully.")
    return client


# ---------------------------------------------------------------------------
# Data fetch
# ---------------------------------------------------------------------------

def fetch_cleaned_observations(supabase: SupabaseClient, table_name: str = "cleaned_observations_table") -> pd.DataFrame:
    """
    Fetches all records from the 'cleaned_observations_table' in Supabase
    using pagination to bypass default row limits, and returns a Pandas DataFrame.
    """
    logger.info(f"Fetching records from Supabase table: '{table_name}'...")
    all_records: List[Any] = []
    page_size = 1000
    start = 0

    while True:
        response = supabase.table(table_name).select("*").range(start, start + page_size - 1).execute()
        data = response.data

        if not data:
            break

        all_records.extend(list(data))
        logger.info(f"Fetched {len(all_records)} records so far...")

        if len(data) < page_size:
            break

        start += page_size

    if not all_records:
        logger.warning(f"No records found in table '{table_name}'.")
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    logger.info(f"Total records retrieved: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def calculate_data_provenance_mix(df_subset: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculates the breakdown of data provenance / airline share for the subset of observations.
    """
    provenance_info: Dict[str, Any] = {}

    if "airline_code" in df_subset.columns:
        airline_counts = df_subset["airline_code"].value_counts().to_dict()
        provenance_info["airlines"] = {str(k): int(v) for k, v in airline_counts.items()}

    provenance_counts: Dict[str, int] = {}
    provenance_columns = [
        column for column in ["data_provenance", "data_provenance_base", "data_provenance_current"]
        if column in df_subset.columns
    ]
    for column in provenance_columns:
        for value in df_subset[column].dropna():
            sources = {source.strip() for source in str(value).split("|") if source.strip()}
            for source in sources:
                provenance_counts[source] = provenance_counts.get(source, 0) + 1
    provenance_info["data_sources"] = dict(sorted(provenance_counts.items()))

    provenance_info["total_matched_pairs"] = len(df_subset)
    return provenance_info


def _format_route_id(route_id: Any) -> str:
    """Safely format route_id (int, float, str, or Hashable) to a clean string."""
    if route_id is None or pd.isna(route_id):
        return ""
    s = str(route_id).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    if s and any(ch.isalpha() for ch in s):
        return s.upper().replace(" ", "")
    return s


def _normalize_booking_window(value: Any) -> str:
    """Standardize booking-window values to the canonical Jevons window labels."""
    if value is None or pd.isna(value):
        return ""
    window = str(value).strip().upper().replace(" ", "")
    return window if window in {"T+1", "T+7", "T+15", "T+30", "T+45"} else ""


def _geometric_mean_fare(series: pd.Series) -> float:
    """Compute the geometric mean of a strictly positive fare series."""
    values = pd.to_numeric(series.dropna(), errors="coerce")
    values = values[values > 0].to_numpy(dtype=float)
    if values.size == 0:
        return float("nan")
    return float(np.exp(np.mean(np.log(values))))


def _aggregate_to_jevons_grain(df: pd.DataFrame, merge_keys: List[str]) -> pd.DataFrame:
    """
    Collapse multiple observations that share the same Jevons analytical grain
    (route_id, airline_code, cabin_class, advance_booking_window) within a single
    observation_date into ONE representative row using:
      - geometric mean of clean_base_fare  (the indexed price variable)
      - sum of observation count           (preserved as n_obs for num_observations_used)
      - concatenated/union data_provenance sources

    This prevents many-to-many fan-out during the base/current merge.
    Multi-source or multi-scrape observations for the same product on the same
    calendar date are legitimately collapsed here — they are NOT silently dropped.
    """
    agg_map: Dict[str, Any] = {
        "clean_base_fare": _geometric_mean_fare,
        "_obs_count": "sum",
    }

    # Carry forward data_provenance as a set string if present
    if "data_provenance" in df.columns:
        agg_map["data_provenance"] = lambda s: "|".join(sorted(s.dropna().unique()))

    # Add a per-row count sentinel before aggregating
    df = df.copy()
    df["_obs_count"] = 1

    aggregated = (
        df.groupby(merge_keys, sort=False, as_index=False)
        .agg(agg_map)
    )
    return aggregated


# ---------------------------------------------------------------------------
# Core Jevons calculation
# ---------------------------------------------------------------------------

def compute_apix_jevons_index(
    df: pd.DataFrame,
    dgca_route_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculates Elementary, Route-level, and National-level APIx Jevons indices.

    Steps:
    1.  Converts observation_date to datetime.
    2.  Validates and filters required columns and positive base fares.
    3.  Identifies base period (earliest observation_date).
    4.  For each current date > base_date:
        a.  Aggregates df_base and df_current to the Jevons grain (geometric mean)
            — prevents many-to-many fan-out.
        b.  Merges with validate="one_to_one" on
            [route_id, airline_code, cabin_class, advance_booking_window].
        c.  Computes price_relative = clean_base_fare_current / clean_base_fare_base.
        d.  Elementary Jevons: exp(mean(log(price_relative))) * 100.
        e.  Route-level rollup: weighted sum across booking windows using WINDOW_WEIGHTS.
        f.  National rollup: weighted sum across routes using dgca_route_weights
            (real DGCA passenger-volume shares — see _load_dgca_route_weights;
            a route missing from this dict falls back to weight 1.0, unweighted).
    5.  Builds payload dicts aligned exactly to index_values schema.

    Index type values are exactly: 'elementary', 'route', 'national'.
    Payload keys: observation_date, base_period_date, index_type, route_id,
                  advance_booking_window, index_value, num_observations_used,
                  data_provenance_mix.
    Note: calculated_at is NOT supplied — the DB DEFAULT NOW() handles it.
    """
    if df.empty:
        logger.error("Empty DataFrame provided for calculation.")
        return []

    dgca_route_weights = dgca_route_weights or {}

    df = df.copy()

    # airline_code must come from the canonical cleaned table column.
    # If it is absent the pipeline is mis-configured — fail early.
    required_cols = [
        "observation_date",
        "route_id",
        "airline_code",
        "cabin_class",
        "advance_booking_window",
        "clean_base_fare",
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(
            f"Missing required columns in cleaned_observations_table: {missing_cols}\n"
            "Ensure the cleaning pipeline has run with the updated cleaned_table.py "
            "that produces an 'airline_code' column."
        )

    # Convert and sanitize
    df = df.copy()
    df["route_id"] = df["route_id"].map(_format_route_id)
    df["airline_code"] = df["airline_code"].map(lambda value: "" if value is None or pd.isna(value) else str(value).strip().upper())
    df["cabin_class"] = df["cabin_class"].map(lambda value: "" if value is None or pd.isna(value) else str(value).strip().lower())
    df["advance_booking_window"] = df["advance_booking_window"].map(_normalize_booking_window)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["clean_base_fare"] = pd.to_numeric(df["clean_base_fare"], errors="coerce")
    df = df.dropna(subset=["clean_base_fare", "route_id", "advance_booking_window", "airline_code", "cabin_class"])
    df = df[df["clean_base_fare"] > 0]

    # Only accept the five canonical booking windows
    valid_windows = {"T+1", "T+7", "T+15", "T+30", "T+45"}
    df = df[df["advance_booking_window"].isin(valid_windows)]

    if df.empty:
        logger.error("No valid observations remain after filtering.")
        return []

    merge_keys = [
        "route_id",
        "airline_code",
        "cabin_class",
        "advance_booking_window",
    ]

    # Base period: earliest date
    base_date = df["observation_date"].min()
    base_date_str = base_date.strftime("%Y-%m-%d")
    logger.info(f"Identified Base Period Date: {base_date_str}")

    df_base_raw = df[df["observation_date"] == base_date].copy()

    distinct_current_dates = sorted(
        [d for d in df["observation_date"].unique() if d > base_date]
    )

    if not distinct_current_dates:
        logger.warning(
            "No observation dates strictly greater than the base date were found. "
            "Evaluating base period against itself (Index = 100.0)."
        )
        distinct_current_dates = [base_date]

    # -----------------------------------------------------------------------
    # Aggregate base period to the Jevons grain ONCE (outside the date loop)
    # -----------------------------------------------------------------------
    df_base_agg = _aggregate_to_jevons_grain(df_base_raw, merge_keys)
    logger.info(
        f"Base period: {len(df_base_raw)} observations collapsed to "
        f"{len(df_base_agg)} unique Jevons grains."
    )

    payload: List[Dict[str, Any]] = []

    for curr_date in distinct_current_dates:
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")
        logger.info(f"\n--- Processing Index for Current Date: {curr_date_str} (Base: {base_date_str}) ---")

        df_current_raw = df[df["observation_date"] == curr_date].copy()

        # -------------------------------------------------------------------
        # Aggregate current period to the Jevons grain
        # -------------------------------------------------------------------
        df_current_agg = _aggregate_to_jevons_grain(df_current_raw, merge_keys)
        logger.info(
            f"Current period: {len(df_current_raw)} observations collapsed to "
            f"{len(df_current_agg)} unique Jevons grains."
        )

        # -------------------------------------------------------------------
        # Merge — validate="one_to_one" catches any residual fan-out
        # -------------------------------------------------------------------
        try:
            merged_df = pd.merge(
                df_base_agg,
                df_current_agg,
                on=merge_keys,
                suffixes=("_base", "_current"),
                validate="one_to_one",
            )
        except pd.errors.MergeError as exc:
            logger.error(
                f"Merge validation failed for {curr_date_str}: {exc}. "
                "This indicates a deduplication bug — skipping date."
            )
            continue

        logger.info(f"Number of matched product grains: {len(merged_df)}")

        if merged_df.empty:
            logger.warning(
                f"No matched observations found between {base_date_str} "
                f"and {curr_date_str}. Skipping date."
            )
            continue

        # Calculate price relative: current / base
        merged_df["price_relative"] = (
            merged_df["clean_base_fare_current"] / merged_df["clean_base_fare_base"]
        )
        # Filter non-positive price relatives
        merged_df = merged_df[merged_df["price_relative"] > 0]

        # Total observations used = sum of all collapsed counts from both periods
        obs_count_col_base = "_obs_count_base" if "_obs_count_base" in merged_df.columns else None
        obs_count_col_curr = "_obs_count_current" if "_obs_count_current" in merged_df.columns else None

        # ---------------------------------------------------------------
        # 1. ELEMENTARY JEVONS INDEX
        #    Grouped by (route_id, advance_booking_window)
        # ---------------------------------------------------------------
        elementary_results = []
        elem_groups = merged_df.groupby(["route_id", "advance_booking_window"])

        for (route_id, window), group in elem_groups:
            log_relatives = np.log(group["price_relative"].values)
            elem_jevons = float(np.exp(np.mean(log_relatives)) * 100.0)

            # num_observations_used = total raw observations that went into this grain
            if obs_count_col_base and obs_count_col_curr:
                n_obs = int(group[obs_count_col_base].sum() + group[obs_count_col_curr].sum())
            else:
                n_obs = len(group) * 2  # fallback: 1 base + 1 current per grain

            prov_mix = calculate_data_provenance_mix(group)

            elementary_results.append({
                "observation_date": curr_date_str,
                "base_period_date": base_date_str,
                "index_type": "elementary",
                "route_id": _format_route_id(route_id),
                "advance_booking_window": str(window),
                "index_value": round(elem_jevons, 4),
                "num_observations_used": n_obs,
                "data_provenance_mix": prov_mix,
                # calculated_at is intentionally omitted — DB DEFAULT NOW() handles it
            })

        logger.info(f"Calculated {len(elementary_results)} Elementary Jevons index values.")

        if not elementary_results:
            continue

        df_elem = pd.DataFrame(elementary_results)

        # ---------------------------------------------------------------
        # 2. ROUTE-LEVEL ROLLUP
        #    Weighted across booking windows per route using WINDOW_WEIGHTS
        # ---------------------------------------------------------------
        route_results = []
        for route_id, r_group in df_elem.groupby("route_id"):
            indices = np.asarray(r_group["index_value"].astype(float).to_numpy(dtype=float), dtype=float)
            windows = r_group["advance_booking_window"].values
            w_arr = np.array([WINDOW_WEIGHTS.get(str(w), 1.0) for w in windows], dtype=float)

            if w_arr.sum() > 0:
                w_norm = w_arr / w_arr.sum()
                route_index_val = float(np.sum(indices * w_norm))
            else:
                route_index_val = float(np.mean(indices))

            route_obs_used = int(r_group["num_observations_used"].sum())

            route_matched_df = merged_df[merged_df["route_id"].astype(str) == str(route_id)]
            route_prov_mix = calculate_data_provenance_mix(route_matched_df)

            route_results.append({
                "observation_date": curr_date_str,
                "base_period_date": base_date_str,
                "index_type": "route",
                "route_id": _format_route_id(route_id),
                "advance_booking_window": None,
                "index_value": round(route_index_val, 4),
                "num_observations_used": route_obs_used,
                "data_provenance_mix": route_prov_mix,
            })

        logger.info(f"Calculated {len(route_results)} Route-level rolled up index values (Booking-Window Weighted).")

        # ---------------------------------------------------------------
        # 3. NATIONAL APIx ROLLUP
        #    Weighted across routes using real DGCA passenger-volume shares
        # ---------------------------------------------------------------
        df_routes = pd.DataFrame(route_results)
        if df_routes.empty:
            logger.warning(f"No route-level results generated for {curr_date_str}; skipping national rollup.")
            continue

        route_indices = np.asarray(df_routes["index_value"].astype(float).to_numpy(dtype=float), dtype=float)
        route_keys = df_routes["route_id"].astype(str).values
        r_weights = np.array([dgca_route_weights.get(rk, 1.0) for rk in route_keys], dtype=float)

        if r_weights.sum() > 0:
            r_weights_norm = r_weights / r_weights.sum()
            national_index_val = float(np.sum(route_indices * r_weights_norm))
        else:
            national_index_val = float(np.mean(route_indices))

        national_obs_used = int(df_routes["num_observations_used"].sum())
        national_prov_mix = calculate_data_provenance_mix(merged_df)

        national_record = {
            "observation_date": curr_date_str,
            "base_period_date": base_date_str,
            "index_type": "national",
            "route_id": None,
            "advance_booking_window": None,
            "index_value": round(national_index_val, 4),
            "num_observations_used": national_obs_used,
            "data_provenance_mix": national_prov_mix,
        }

        logger.info(f"National APIx Index Value: {national_record['index_value']} (Obs: {national_obs_used}, DGCA Traffic Weighted)")

        payload.extend(elementary_results)
        payload.extend(route_results)
        payload.append(national_record)

    return payload


# ---------------------------------------------------------------------------
# DB write — idempotent, via psycopg2/DATABASE_URL
# ---------------------------------------------------------------------------
#
# Writes go through the same privileged DATABASE_URL connection the rest of
# this project's backend already uses (backend/app/db/connection.py),
# rather than the Supabase REST client with an anon/service-role key. This
# avoids needing a separate service_role credential just for this one write
# path, and matches how every other write in this project already works.

def push_to_supabase(
    payload: List[Dict[str, Any]],
    table_name: str = "index_values",
) -> int:
    """
    Idempotently inserts the computed index payload into the `index_values`
    table via psycopg2.

    Idempotency guarantee:
      1. Collect all unique observation_date values from the payload.
      2. Delete ALL existing index_values rows for those dates in ONE operation.
      3. Insert the newly computed records in one batch.

    This means re-running the engine for the same dates produces exactly the
    same set of rows — no duplicate history accumulates.

    Payload schema contract:
      observation_date, base_period_date, index_type, route_id,
      advance_booking_window, index_value, num_observations_used,
      data_provenance_mix.
    Note: calculated_at is not supplied — the DB DEFAULT NOW() populates it.
    """
    if not payload:
        logger.warning("Payload is empty. Nothing to insert into the database.")
        return 0

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is not set — cannot write index_values.")

    observation_dates = sorted({row["observation_date"] for row in payload})
    logger.info(
        f"Deleting existing index_values rows for {len(observation_dates)} observation date(s): "
        f"{observation_dates}"
    )

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {table_name} WHERE observation_date = ANY(%s::date[])",
                (observation_dates,),
            )
            logger.info(f"Deleted {cur.rowcount} existing row(s). Proceeding with fresh insert.")

            insert_sql = f"""
                INSERT INTO {table_name} (
                    observation_date, base_period_date, index_type, route_id,
                    advance_booking_window, index_value, num_observations_used,
                    data_provenance_mix
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            rows = [
                (
                    item["observation_date"],
                    item["base_period_date"],
                    item["index_type"],
                    item.get("route_id"),
                    item.get("advance_booking_window"),
                    item["index_value"],
                    item["num_observations_used"],
                    json.dumps(item.get("data_provenance_mix")),
                )
                for item in payload
            ]
            cur.executemany(insert_sql, rows)
            inserted = cur.rowcount if cur.rowcount != -1 else len(rows)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    logger.info(f"Successfully pushed {len(payload)} index records to '{table_name}'.")
    return len(payload)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Main execution pipeline for the Jevons Cloud Engine."""
    print("=" * 75)
    print("      APIx JEVONS INDEX ENGINE (CLOUD EXECUTION) - STUDENT ID: 25BCE355")
    print("=" * 75)

    try:
        load_dotenv()

        # Step 1: Initialize Supabase client (used for reads only)
        supabase = get_supabase_client()

        # Step 2: Fetch cleaned observations from the canonical table
        df_observations = fetch_cleaned_observations(supabase, table_name="cleaned_observations_table")

        if df_observations.empty:
            logger.error(
                "No observations available to process. "
                "Ensure the cleaning pipeline has been run first."
            )
            return

        # Step 3: Load real DGCA route-traffic weights from the DB
        dgca_route_weights = _load_dgca_route_weights()

        # Step 4: Compute APIx Jevons Index (Elementary → Route → National)
        payload = compute_apix_jevons_index(df_observations, dgca_route_weights=dgca_route_weights)

        if not payload:
            logger.warning("No index records were generated. Exiting.")
            return

        # Step 5: Visual Verification — Print Payload Summary & Sample Records
        print("\n" + "=" * 75)
        print("                       FINAL PAYLOAD SUMMARY")
        print("=" * 75)
        df_summary = pd.DataFrame(payload)

        type_counts = df_summary["index_type"].value_counts().to_dict()
        print(f"Total Generated Records: {len(payload)}")
        print(f"Record Counts by Index Type: {json.dumps(type_counts, indent=2)}")
        print("\nSample Generated Records (Top 5):")
        print(json.dumps(payload[:5], indent=2, default=str))

        if len(payload) > 5:
            print("\nNational Level Record:")
            national_records = [r for r in payload if r.get("index_type") == "national"]
            if national_records:
                print(json.dumps(national_records[0], indent=2, default=str))

        print("=" * 75)

        # Step 6: Idempotently push to the database
        push_to_supabase(payload, table_name="index_values")
        print("\n[SUCCESS] Jevons Index calculation and cloud upload completed successfully.")

    except Exception as e:
        logger.exception(f"Engine execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
