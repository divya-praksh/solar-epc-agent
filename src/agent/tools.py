"""Tool definitions for the Claude tool-use agent loop (PRD Section 6).

Each tool has a Python function here that takes a db connection plus plain
arguments and returns JSON-serializable data, and an entry in TOOL_SCHEMAS
(the Anthropic tool-use schema Claude actually sees). TOOL_FUNCTIONS maps
tool name -> function for the agent loop (Week 3, Days 12-13) to dispatch on.

The two compute_* tools fetch rows from the DB and hand plain values to the
pure functions in src/compute/ -- the LLM never generates a number, it only
ever sees numbers this file computed. The two draft_* tools write a row to
agent_recommendations but never mark it committed; only the HITL UI does
that on human approval.
"""

import datetime
import json

from src.compute.priority_score import calculate_priority_score, rank_by_priority
from src.compute.reorder import calculate_eoq, calculate_reorder_point, reorder_recommendation

ORDER_COST = 5000  # INR, flat per-PO estimate, matches src/compute/__main__.py
HOLDING_COST_RATE = 0.2  # 20% of unit price per year


def _days_until(iso_date: str) -> int:
    return max((datetime.date.fromisoformat(iso_date) - datetime.date.today()).days, 0)


def get_stock_position(conn, item_id: str) -> dict:
    rows = conn.execute(
        "SELECT warehouse_id, qty_on_hand, qty_reserved, qty_in_transit FROM stock WHERE item_id = ?",
        (item_id,),
    ).fetchall()
    if not rows:
        raise ValueError(f"no stock rows for item_id={item_id}")

    return {
        "item_id": item_id,
        "warehouses": [dict(r) for r in rows],
        "total_on_hand": sum(r["qty_on_hand"] for r in rows),
        "total_reserved": sum(r["qty_reserved"] for r in rows),
        "total_in_transit": sum(r["qty_in_transit"] for r in rows),
    }


def get_project_schedule(conn, project_id: str) -> dict:
    project = conn.execute(
        "SELECT project_id, name, cod_deadline FROM projects WHERE project_id = ?", (project_id,)
    ).fetchone()
    if project is None:
        raise ValueError(f"no project with project_id={project_id}")

    milestones = conn.execute(
        "SELECT item_id, qty_required, milestone_date FROM bom WHERE project_id = ? ORDER BY milestone_date",
        (project_id,),
    ).fetchall()

    return {
        "project_id": project["project_id"],
        "name": project["name"],
        "cod_deadline": project["cod_deadline"],
        "milestones": [dict(m) for m in milestones],
    }


def get_contract_context(conn, project_id: str) -> dict:
    project = conn.execute(
        "SELECT project_id, contract_value, contract_notes_text FROM projects WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    if project is None:
        raise ValueError(f"no project with project_id={project_id}")

    return dict(project)


def get_supplier_options(conn, item_id: str) -> dict:
    rows = conn.execute(
        "SELECT supplier_id, lead_time_days, unit_price, notes_text FROM suppliers WHERE item_id = ?",
        (item_id,),
    ).fetchall()
    if not rows:
        raise ValueError(f"no suppliers for item_id={item_id}")

    return {"item_id": item_id, "suppliers": [dict(r) for r in rows]}


def compute_reorder_point(conn, item_id: str, safety_stock: float = 0.0) -> dict:
    stock = get_stock_position(conn, item_id)
    available = stock["total_on_hand"] + stock["total_in_transit"]

    bom_rows = conn.execute(
        "SELECT qty_required, milestone_date FROM bom WHERE item_id = ?", (item_id,)
    ).fetchall()
    suppliers = conn.execute(
        "SELECT lead_time_days, unit_price FROM suppliers WHERE item_id = ?", (item_id,)
    ).fetchall()
    if not bom_rows or not suppliers:
        raise ValueError(f"insufficient BOM/supplier data to compute reorder point for item_id={item_id}")

    total_demand = sum(r["qty_required"] for r in bom_rows)
    nearest_milestone = min(r["milestone_date"] for r in bom_rows)
    days_out = max(_days_until(nearest_milestone), 1)
    daily_demand = total_demand / days_out

    lead_time_days = min(r["lead_time_days"] for r in suppliers)
    avg_price = sum(r["unit_price"] for r in suppliers) / len(suppliers)

    rop = calculate_reorder_point(daily_demand=daily_demand, lead_time_days=lead_time_days, safety_stock=safety_stock)
    eoq = calculate_eoq(
        annual_demand=daily_demand * 365, order_cost=ORDER_COST, holding_cost_per_unit=avg_price * HOLDING_COST_RATE
    )
    recommendation = reorder_recommendation(available_stock=available, reorder_point=rop, eoq_qty=eoq)

    return {
        "item_id": item_id,
        "available_stock": available,
        "daily_demand": round(daily_demand, 2),
        "lead_time_days": lead_time_days,
        "reorder_point": round(rop, 2),
        "eoq": round(eoq, 2),
        **recommendation,
    }


def compute_priority_scores(conn, project_ids: list, item_id: str) -> dict:
    scores = {}
    for project_id in project_ids:
        reservation = conn.execute(
            "SELECT priority_inputs_json FROM reservations WHERE project_id = ? AND item_id = ?",
            (project_id, item_id),
        ).fetchone()
        if reservation is None:
            raise ValueError(f"no reservation for project_id={project_id}, item_id={item_id}")

        bom_row = conn.execute(
            "SELECT milestone_date FROM bom WHERE project_id = ? AND item_id = ?",
            (project_id, item_id),
        ).fetchone()
        if bom_row is None:
            raise ValueError(f"no BOM row for project_id={project_id}, item_id={item_id}")

        days_to_deadline = _days_until(bom_row["milestone_date"])
        inputs = json.loads(reservation["priority_inputs_json"])
        scores[project_id] = round(calculate_priority_score(days_to_deadline=days_to_deadline, **inputs), 2)

    return {
        "item_id": item_id,
        "scores": scores,
        "ranking": [project_id for project_id, _ in rank_by_priority(scores)],
    }


def draft_purchase_order(conn, item_id: str, qty: float, supplier_id: str, llm_reasoning_text: str) -> dict:
    """Writes a draft row. Never submitted -- a human must approve it in the
    HITL UI (Week 4) before it becomes a real PO."""
    formula_output = compute_reorder_point(conn, item_id)
    cursor = conn.execute(
        "INSERT INTO agent_recommendations (type, item_id, project_ids, formula_output_json, llm_reasoning_text) "
        "VALUES ('reorder', ?, '[]', ?, ?)",
        (item_id, json.dumps({**formula_output, "qty": qty, "supplier_id": supplier_id}), llm_reasoning_text),
    )
    conn.commit()
    return {"recommendation_id": cursor.lastrowid, "status": "drafted"}


def draft_allocation_plan(conn, item_id: str, allocations: dict, llm_reasoning_text: str) -> dict:
    """Writes a draft row. Never submitted -- a human must approve it in the
    HITL UI (Week 4) before it becomes a committed allocation."""
    project_ids = list(allocations.keys())
    formula_output = compute_priority_scores(conn, project_ids, item_id)
    cursor = conn.execute(
        "INSERT INTO agent_recommendations (type, item_id, project_ids, formula_output_json, llm_reasoning_text) "
        "VALUES ('allocation', ?, ?, ?, ?)",
        (item_id, json.dumps(project_ids), json.dumps({**formula_output, "allocations": allocations}), llm_reasoning_text),
    )
    conn.commit()
    return {"recommendation_id": cursor.lastrowid, "status": "drafted"}


TOOL_SCHEMAS = [
    {
        "name": "get_stock_position",
        "description": "Get current on-hand, reserved, and in-transit stock for an item across all warehouses.",
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "get_project_schedule",
        "description": "Get a project's COD deadline and its BOM milestones (item, quantity, milestone date).",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "get_contract_context",
        "description": (
            "Get a project's contract value and raw contract notes text -- the unstructured field that may "
            "contain clauses (e.g. force-majeure carve-outs) a formula score can't see."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "get_supplier_options",
        "description": (
            "Get all suppliers for an item: lead time, unit price, and raw notes text -- the unstructured "
            "field that may contain reliability history a formula score can't see."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}},
            "required": ["item_id"],
        },
    },
    {
        "name": "compute_reorder_point",
        "description": (
            "Deterministically compute the reorder point, EOQ, and reorder recommendation for an item from "
            "current stock, BOM demand, and supplier lead time. Never estimate this number yourself -- always "
            "call this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "safety_stock": {"type": "number", "description": "Optional safety stock buffer, defaults to 0."},
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "compute_priority_scores",
        "description": (
            "Deterministically compute the weighted priority score for each competing project's reservation "
            "on a shared item, and rank them. This is a starting score only -- unstructured contract/supplier "
            "context may justify overriding this ranking. Never estimate this number yourself -- always call "
            "this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_ids": {"type": "array", "items": {"type": "string"}},
                "item_id": {"type": "string"},
            },
            "required": ["project_ids", "item_id"],
        },
    },
    {
        "name": "draft_purchase_order",
        "description": (
            "Draft a purchase order for human review. This does NOT submit the PO -- it only saves a draft "
            "recommendation that a human must approve in the UI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "qty": {"type": "number"},
                "supplier_id": {"type": "string"},
                "llm_reasoning_text": {"type": "string", "description": "Your reasoning for this recommendation."},
            },
            "required": ["item_id", "qty", "supplier_id", "llm_reasoning_text"],
        },
    },
    {
        "name": "draft_allocation_plan",
        "description": (
            "Draft an allocation plan for human review. This does NOT commit the allocation -- it only saves "
            "a draft recommendation that a human must approve in the UI."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "allocations": {
                    "type": "object",
                    "description": "Map of project_id -> allocated quantity.",
                },
                "llm_reasoning_text": {"type": "string", "description": "Your reasoning for this allocation."},
            },
            "required": ["item_id", "allocations", "llm_reasoning_text"],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_stock_position": get_stock_position,
    "get_project_schedule": get_project_schedule,
    "get_contract_context": get_contract_context,
    "get_supplier_options": get_supplier_options,
    "compute_reorder_point": compute_reorder_point,
    "compute_priority_scores": compute_priority_scores,
    "draft_purchase_order": draft_purchase_order,
    "draft_allocation_plan": draft_allocation_plan,
}
