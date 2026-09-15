"""
Fee decomposition: splits a displayed total fare (raw_price_displayed) into
base_fare / taxes_fees / udf / fuel_surcharge / gst_amount using the
airline_tax_schedule table (real per-station tariff-sheet data - never
fabricated; rows with no matching schedule are left undecomposed).

Formula reverse-engineered from Phase 3's original manual backfill and
verified to exactly reproduce all 1,038 of its rows (0 mismatches on every
component): at the flight's ORIGIN station, every airline_tax_schedule row
except GST and any UDF* code sums into taxes_fees; every UDF* code sums into
udf; a YQ code (if present) is the flat fuel_surcharge; GST is a percentage
of base_fare. base_fare is then the residual:

    base_fare = (raw_price_displayed - taxes_fees - udf - fuel_surcharge) / (1 + gst_rate)
    gst_amount = round(base_fare * gst_rate, 2)

Used both to backfill existing rows (see backfill_fee_decomposition.py) and
to decompose newly-scraped rows at insert time (see app/db/queries.py).
"""
import logging

logger = logging.getLogger(__name__)


def _aggregate_schedule(rows):
    """rows: iterable of (tax_code, amount, is_percentage). Returns the
    (taxes_fees, udf, fuel_surcharge, gst_rate) buckets, or None if there's
    no GST percentage row (schedule is unusable without it)."""
    taxes_fees = 0.0
    udf = 0.0
    fuel_surcharge = None
    gst_rate = None

    for tax_code, amount, is_percentage in rows:
        amount = float(amount)
        code = (tax_code or "").upper()
        if code == "GST" and is_percentage:
            gst_rate = amount / 100.0
        elif code == "YQ":
            fuel_surcharge = amount
        elif code.startswith("UDF"):
            udf += amount
        else:
            taxes_fees += amount

    if gst_rate is None:
        return None

    return round(taxes_fees, 2), round(udf, 2), fuel_surcharge, gst_rate


def decompose_fare(schedule_rows, raw_price_displayed):
    """
    schedule_rows: airline_tax_schedule rows (tax_code, amount, is_percentage)
    for one (airline_name, origin_station) pair - caller looks these up.
    raw_price_displayed: the total price actually shown to the user.

    Returns a dict of {base_fare, fuel_surcharge, taxes_fees, gst_amount,
    udf, fee_derivation}, or None if decomposition can't be honestly done
    (no schedule, no GST rate, or the fixed fees exceed the total price).
    """
    if not schedule_rows:
        return None

    aggregated = _aggregate_schedule(schedule_rows)
    if aggregated is None:
        logger.warning("Tariff schedule has no GST percentage row; skipping decomposition")
        return None
    taxes_fees, udf, fuel_surcharge, gst_rate = aggregated

    raw_price = float(raw_price_displayed)
    fixed_total = taxes_fees + udf + (fuel_surcharge or 0.0)
    residual = raw_price - fixed_total
    if residual <= 0:
        logger.warning(
            f"Fixed fees ({fixed_total}) >= displayed price ({raw_price}); skipping decomposition"
        )
        return None

    base_fare = round(residual / (1 + gst_rate), 2)
    gst_amount = round(base_fare * gst_rate, 2)

    return {
        "base_fare": base_fare,
        "fuel_surcharge": fuel_surcharge,
        "taxes_fees": taxes_fees,
        "gst_amount": gst_amount,
        "udf": udf,
        "fee_derivation": "derived_from_tariff_sheet",
    }


def load_schedule(conn, airline_name: str, station: str):
    """Fetches the tariff-sheet rows for one airline/station from the DB."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT tax_code, amount, is_percentage
            FROM airline_tax_schedule
            WHERE airline_name = %s AND station = %s
            """,
            (airline_name, station),
        )
        return cursor.fetchall()
