"""
Standalone, isolated tests for the weighting logic in jevons_engine_cloud.py.
No real network/DB access - synthetic data only, so these actually exercise
the weighting arithmetic (the live cleaned_observations_table snapshot only
has one date, so every real run trivially produces index=100.0 everywhere
and never proves the weighting math is doing anything).

Run: python test_weighting.py
"""
import math

import numpy as np
import pandas as pd

from jevons_engine_cloud import compute_apix_jevons_index, WINDOW_WEIGHTS


def make_df(rows):
    return pd.DataFrame(rows)


def test_national_rollup_uses_real_dgca_weights_not_equal_average():
    """
    Two routes with clearly different price movements (route 2 doubles,
    route 6 stays flat). If DGCA weighting is really being applied, the
    national index must land near route 2's value when route 2 is given
    almost all the weight - NOT the unweighted midpoint (which is what the
    bug being fixed here produced).
    """
    rows = []
    for route_id, base_price, curr_price in [(2, 5000.0, 10000.0), (6, 5000.0, 5000.0)]:
        rows.append({
            "observation_date": "2026-01-01", "route_id": route_id, "airline_code": "6E",
            "cabin_class": "economy", "advance_booking_window": "T+30", "clean_base_fare": base_price,
        })
        rows.append({
            "observation_date": "2026-01-08", "route_id": route_id, "airline_code": "6E",
            "cabin_class": "economy", "advance_booking_window": "T+30", "clean_base_fare": curr_price,
        })
    df = make_df(rows)

    # Route 2 gets 95% of the weight, route 6 gets 5% - almost all weight on
    # the route that doubled, so the national index should land close to 200,
    # not at the unweighted midpoint of 150.
    dgca_weights = {"2": 0.95, "6": 0.05}
    payload = compute_apix_jevons_index(df, dgca_route_weights=dgca_weights)

    national = [r for r in payload if r["index_type"] == "national"][0]
    route2 = [r for r in payload if r["index_type"] == "route" and r["route_id"] == "2"][0]
    route6 = [r for r in payload if r["index_type"] == "route" and r["route_id"] == "6"][0]

    assert math.isclose(route2["index_value"], 200.0, rel_tol=1e-3), route2
    assert math.isclose(route6["index_value"], 100.0, rel_tol=1e-3), route6

    expected_national = 0.95 * 200.0 + 0.05 * 100.0  # = 195.0
    assert math.isclose(national["index_value"], expected_national, rel_tol=1e-3), (
        f"National index {national['index_value']} should be close to the "
        f"DGCA-weighted value {expected_national}, not the unweighted "
        f"midpoint 150.0 (that was the bug)."
    )
    print(f"PASS: national index = {national['index_value']} "
          f"(expected ~{expected_national}, unweighted midpoint would be 150.0)")


def test_route_missing_from_dgca_weights_falls_back_to_unweighted_not_dropped():
    """
    A route absent from the DGCA weights dict (e.g. AMD-DEL, which has no
    DGCA figure on file) must still be included in the national rollup with
    a neutral weight of 1.0 - never silently dropped, never crash.
    """
    rows = []
    for route_id, base_price, curr_price in [(2, 5000.0, 5500.0), (8, 4000.0, 4000.0)]:
        rows.append({
            "observation_date": "2026-01-01", "route_id": route_id, "airline_code": "AI",
            "cabin_class": "economy", "advance_booking_window": "T+1", "clean_base_fare": base_price,
        })
        rows.append({
            "observation_date": "2026-01-08", "route_id": route_id, "airline_code": "AI",
            "cabin_class": "economy", "advance_booking_window": "T+1", "clean_base_fare": curr_price,
        })
    df = make_df(rows)

    # Route 8 (AMD-DEL) deliberately absent - matches the live DB today.
    dgca_weights = {"2": 0.7}
    payload = compute_apix_jevons_index(df, dgca_route_weights=dgca_weights)

    route_ids_in_national_calc = {r["route_id"] for r in payload if r["index_type"] == "route"}
    assert "8" in route_ids_in_national_calc, "Route missing from DGCA weights was dropped, not just unweighted"
    print("PASS: route absent from DGCA weights still appears in the rollup (unweighted fallback)")


def test_booking_window_weighting_differs_from_plain_mean():
    """
    One route, two windows with different price movements. WINDOW_WEIGHTS
    gives T+7 (0.28) much more weight than T+45 (0.18) - confirm the
    route-level rollup is NOT a plain unweighted mean of the two windows.
    """
    rows = []
    for window, base_price, curr_price in [("T+7", 4000.0, 6000.0), ("T+45", 4000.0, 4000.0)]:
        rows.append({
            "observation_date": "2026-01-01", "route_id": 2, "airline_code": "6E",
            "cabin_class": "economy", "advance_booking_window": window, "clean_base_fare": base_price,
        })
        rows.append({
            "observation_date": "2026-01-08", "route_id": 2, "airline_code": "6E",
            "cabin_class": "economy", "advance_booking_window": window, "clean_base_fare": curr_price,
        })
    df = make_df(rows)

    payload = compute_apix_jevons_index(df, dgca_route_weights={"2": 1.0})
    route = [r for r in payload if r["index_type"] == "route"][0]

    plain_mean = (150.0 + 100.0) / 2  # 125.0 - what an unweighted mean would give
    w7, w45 = WINDOW_WEIGHTS["T+7"], WINDOW_WEIGHTS["T+45"]
    expected = (150.0 * w7 + 100.0 * w45) / (w7 + w45)

    assert not math.isclose(route["index_value"], plain_mean, abs_tol=0.5), (
        f"Route index {route['index_value']} matches the unweighted mean {plain_mean} - "
        f"booking-window weighting isn't being applied."
    )
    assert math.isclose(route["index_value"], expected, rel_tol=1e-3), route
    print(f"PASS: route index = {route['index_value']} (weighted, not the plain mean {plain_mean})")


def test_empty_dataframe_returns_empty_payload_not_crash():
    payload = compute_apix_jevons_index(pd.DataFrame(), dgca_route_weights={"2": 1.0})
    assert payload == []
    print("PASS: empty input -> empty payload, no crash")


def test_missing_required_column_raises_keyerror_not_silent_wrong_output():
    df = make_df([{
        "observation_date": "2026-01-01", "route_id": 2, "cabin_class": "economy",
        "advance_booking_window": "T+1", "clean_base_fare": 5000.0,
        # airline_code deliberately omitted
    }])
    try:
        compute_apix_jevons_index(df, dgca_route_weights={})
        raise AssertionError("Expected KeyError for missing airline_code column")
    except KeyError:
        print("PASS: missing required column raises KeyError instead of silently producing wrong output")


def test_single_observation_per_grain_geometric_mean_is_well_defined():
    """Elementary Jevons with exactly one matched pair must not divide by zero / NaN."""
    df = make_df([
        {"observation_date": "2026-01-01", "route_id": 2, "airline_code": "AI", "cabin_class": "economy",
         "advance_booking_window": "T+1", "clean_base_fare": 5000.0},
        {"observation_date": "2026-01-02", "route_id": 2, "airline_code": "AI", "cabin_class": "economy",
         "advance_booking_window": "T+1", "clean_base_fare": 5250.0},
    ])
    payload = compute_apix_jevons_index(df, dgca_route_weights={"2": 1.0})
    elem = [r for r in payload if r["index_type"] == "elementary"][0]
    assert math.isclose(elem["index_value"], 105.0, rel_tol=1e-3), elem
    assert not np.isnan(elem["index_value"])
    print(f"PASS: single-pair elementary index = {elem['index_value']} (expected 105.0)")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    if failures:
        raise SystemExit(1)
