"""Weighted priority score for allocation decisions (PRD Section 3). Pure
function: plain numbers in, plain number out, no database access.

This is deliberately a *starting* score, not the final word -- the LLM's job
(Week 3) is to reason over this score plus unstructured context (contract
clauses, schedule notes) that these four numbers can't see. Default weights
are scaled so each term contributes a comparable range for the magnitudes
seen in seed data (src/db/seed_data.py): they're a demo starting point, not a
validated calibration.
"""

DEFAULT_WEIGHTS = {
    "deadline": -1.0,  # points per day; negative so a closer deadline scores higher
    "revenue": 1e-6,  # points per rupee of revenue at risk
    "penalty": 100.0,  # points per unit of penalty_exposure_pct_per_day
    "delay": 100.0,  # points per unit of delay_probability (0-1)
}


def calculate_priority_score(
    days_to_deadline: float,
    revenue_at_risk: float,
    penalty_exposure: float,
    delay_probability: float,
    weights: dict = None,
) -> float:
    if days_to_deadline < 0:
        raise ValueError("days_to_deadline must be non-negative")
    if revenue_at_risk < 0:
        raise ValueError("revenue_at_risk must be non-negative")
    if penalty_exposure < 0:
        raise ValueError("penalty_exposure must be non-negative")
    if not 0 <= delay_probability <= 1:
        raise ValueError("delay_probability must be between 0 and 1")

    w = weights if weights is not None else DEFAULT_WEIGHTS

    return (
        w["deadline"] * days_to_deadline
        + w["revenue"] * revenue_at_risk
        + w["penalty"] * penalty_exposure
        + w["delay"] * delay_probability
    )


def rank_by_priority(scores: dict) -> list:
    """Sorts {project_id: score} descending (highest priority first). Python's
    sort is stable, so ties keep their input order -- breaking a real tie is
    the LLM's job (PRD Section 3), not this function's."""
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
