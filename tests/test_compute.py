"""Unit tests for the deterministic compute layer. Includes known-good
formula checks and tests grounded directly in the two scripted scenarios
from seed_data.py, so drift in the seed data would break these too.
"""

import json

import pytest

from src.compute.priority_score import calculate_priority_score, rank_by_priority
from src.compute.reorder import calculate_eoq, calculate_reorder_point, reorder_recommendation
from src.db.seed_data import RESERVATIONS, SUPPLIERS


# --- calculate_eoq ---------------------------------------------------------

def test_eoq_known_value():
    # sqrt(2 * 10000 * 100 / 2) = sqrt(1_000_000) = 1000
    assert calculate_eoq(annual_demand=10000, order_cost=100, holding_cost_per_unit=2) == 1000.0


def test_eoq_zero_demand_is_zero():
    assert calculate_eoq(annual_demand=0, order_cost=100, holding_cost_per_unit=2) == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(annual_demand=-1, order_cost=100, holding_cost_per_unit=2),
        dict(annual_demand=100, order_cost=0, holding_cost_per_unit=2),
        dict(annual_demand=100, order_cost=-5, holding_cost_per_unit=2),
        dict(annual_demand=100, order_cost=100, holding_cost_per_unit=0),
        dict(annual_demand=100, order_cost=100, holding_cost_per_unit=-2),
    ],
)
def test_eoq_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        calculate_eoq(**kwargs)


# --- calculate_reorder_point ------------------------------------------------

def test_reorder_point_known_value():
    assert calculate_reorder_point(daily_demand=50, lead_time_days=18, safety_stock=100) == 1000


def test_reorder_point_defaults_to_no_safety_stock():
    assert calculate_reorder_point(daily_demand=50, lead_time_days=18) == 900


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(daily_demand=-1, lead_time_days=18),
        dict(daily_demand=50, lead_time_days=-1),
        dict(daily_demand=50, lead_time_days=18, safety_stock=-1),
    ],
)
def test_reorder_point_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        calculate_reorder_point(**kwargs)


# --- reorder_recommendation --------------------------------------------------

def test_reorder_recommendation_triggers_below_rop():
    result = reorder_recommendation(available_stock=500, reorder_point=1000, eoq_qty=1000.0)
    assert result == {"should_reorder": True, "reorder_qty": 1000.0}


def test_reorder_recommendation_triggers_at_exact_rop():
    result = reorder_recommendation(available_stock=1000, reorder_point=1000, eoq_qty=1000.0)
    assert result["should_reorder"] is True


def test_reorder_recommendation_skips_above_rop():
    result = reorder_recommendation(available_stock=1500, reorder_point=1000, eoq_qty=1000.0)
    assert result == {"should_reorder": False, "reorder_qty": 0.0}


# --- calculate_priority_score -----------------------------------------------

def test_priority_score_known_value():
    score = calculate_priority_score(
        days_to_deadline=60, revenue_at_risk=40_000_000, penalty_exposure=0.3, delay_probability=0.3
    )
    # -1*60 + 1e-6*40_000_000 + 100*0.3 + 100*0.3 = -60 + 40 + 30 + 30 = 40
    assert score == 40.0


def test_priority_score_closer_deadline_scores_higher_all_else_equal():
    near = calculate_priority_score(
        days_to_deadline=10, revenue_at_risk=1_000_000, penalty_exposure=0.2, delay_probability=0.2
    )
    far = calculate_priority_score(
        days_to_deadline=100, revenue_at_risk=1_000_000, penalty_exposure=0.2, delay_probability=0.2
    )
    assert near > far


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(days_to_deadline=-1, revenue_at_risk=1000, penalty_exposure=0.1, delay_probability=0.1),
        dict(days_to_deadline=10, revenue_at_risk=-1, penalty_exposure=0.1, delay_probability=0.1),
        dict(days_to_deadline=10, revenue_at_risk=1000, penalty_exposure=-0.1, delay_probability=0.1),
        dict(days_to_deadline=10, revenue_at_risk=1000, penalty_exposure=0.1, delay_probability=-0.1),
        dict(days_to_deadline=10, revenue_at_risk=1000, penalty_exposure=0.1, delay_probability=1.1),
    ],
)
def test_priority_score_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        calculate_priority_score(**kwargs)


def test_rank_by_priority_orders_descending():
    ranked = rank_by_priority({"A": 10.0, "B": 30.0, "C": 20.0})
    assert ranked == [("B", 30.0), ("C", 20.0), ("A", 10.0)]


def test_rank_by_priority_preserves_order_on_ties():
    ranked = rank_by_priority({"A": 10.0, "B": 10.0, "C": 10.0})
    assert [project_id for project_id, _ in ranked] == ["A", "B", "C"]


# --- Scenario 1 (force-majeure allocation tie) grounded in seed data --------

def _reservation_inputs(project_id: str, item_id: str) -> dict:
    for row_project_id, row_item_id, _qty, priority_inputs_json in RESERVATIONS:
        if row_project_id == project_id and row_item_id == item_id:
            return json.loads(priority_inputs_json)
    raise AssertionError(f"no reservation for {project_id}/{item_id}")


def test_scenario_1_priority_score_ties_exactly():
    bhadla_inputs = _reservation_inputs("PRJ-BHADLA2", "ITM-INVCTL")
    pavagada_inputs = _reservation_inputs("PRJ-PAVAGADA", "ITM-INVCTL")
    assert bhadla_inputs == pavagada_inputs, "seed data must keep these tied for the scenario to hold"

    # Both BOM rows share a milestone date (see seed_data.py), so days_to_deadline
    # is identical too -- any fixed value demonstrates the tie holds.
    days_to_deadline = 59

    score_bhadla = calculate_priority_score(days_to_deadline=days_to_deadline, **bhadla_inputs)
    score_pavagada = calculate_priority_score(days_to_deadline=days_to_deadline, **pavagada_inputs)

    assert score_bhadla == score_pavagada
    assert rank_by_priority({"PRJ-BHADLA2": score_bhadla, "PRJ-PAVAGADA": score_pavagada}) == [
        ("PRJ-BHADLA2", score_bhadla),
        ("PRJ-PAVAGADA", score_pavagada),
    ]


# --- Scenario 2 (stale-supplier reorder tie) grounded in seed data ---------

def _supplier_row(supplier_id: str, item_id: str) -> tuple:
    for row_supplier_id, row_item_id, lead_time_days, unit_price, notes_text in SUPPLIERS:
        if row_supplier_id == supplier_id and row_item_id == item_id:
            return lead_time_days, unit_price, notes_text
    raise AssertionError(f"no supplier row for {supplier_id}/{item_id}")


def test_scenario_2_reorder_point_ties_across_tied_suppliers():
    bharat_lead_time, bharat_price, _ = _supplier_row("SUP-BHARAT", "ITM-MOD540")
    north_lead_time, north_price, _ = _supplier_row("SUP-NORTH", "ITM-MOD540")
    assert bharat_lead_time == north_lead_time, "seed data must keep lead time tied for the scenario to hold"
    assert bharat_price == north_price, "seed data must keep price tied for the scenario to hold"

    daily_demand = 1500
    rop_bharat = calculate_reorder_point(daily_demand=daily_demand, lead_time_days=bharat_lead_time)
    rop_north = calculate_reorder_point(daily_demand=daily_demand, lead_time_days=north_lead_time)

    assert rop_bharat == rop_north, "a formula alone can't break this tie -- that's the point of the scenario"
