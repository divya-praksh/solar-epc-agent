"""Reorder point and EOQ formulas. Pure functions: plain numbers in, plain
numbers out, no database access. Callers (agent tools, CLI, tests) are
responsible for deriving demand rates and costs from the DB.
"""

import math


def calculate_eoq(annual_demand: float, order_cost: float, holding_cost_per_unit: float) -> float:
    """Wilson EOQ: the order quantity that minimizes ordering + holding cost."""
    if annual_demand < 0:
        raise ValueError("annual_demand must be non-negative")
    if order_cost <= 0:
        raise ValueError("order_cost must be positive")
    if holding_cost_per_unit <= 0:
        raise ValueError("holding_cost_per_unit must be positive")

    return math.sqrt((2 * annual_demand * order_cost) / holding_cost_per_unit)


def calculate_reorder_point(daily_demand: float, lead_time_days: float, safety_stock: float = 0.0) -> float:
    """Stock level at which a new order must be placed to avoid running out
    before the replacement arrives."""
    if daily_demand < 0:
        raise ValueError("daily_demand must be non-negative")
    if lead_time_days < 0:
        raise ValueError("lead_time_days must be non-negative")
    if safety_stock < 0:
        raise ValueError("safety_stock must be non-negative")

    return daily_demand * lead_time_days + safety_stock


def reorder_recommendation(available_stock: float, reorder_point: float, eoq_qty: float) -> dict:
    """Combines reorder point and EOQ into the decision a reorder tool needs:
    whether to reorder now, and how much."""
    should_reorder = available_stock <= reorder_point
    return {
        "should_reorder": should_reorder,
        "reorder_qty": eoq_qty if should_reorder else 0.0,
    }
