"""Smoke tests for src/agent/tools.py against a freshly seeded in-memory DB.
Not exhaustive -- the goal is to catch DB/compute-layer wiring bugs (see the
key-name mismatch Day 8 caught) before the agent loop depends on this.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from src.agent.tools import (
    TOOL_FUNCTIONS,
    TOOL_SCHEMAS,
    compute_priority_scores,
    compute_reorder_point,
    draft_allocation_plan,
    draft_purchase_order,
    get_contract_context,
    get_project_schedule,
    get_stock_position,
    get_supplier_options,
)
from src.db.seed_data import seed

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "src" / "db" / "schema.sql"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text())
    seed(connection)
    yield connection
    connection.close()


def test_get_stock_position(conn):
    result = get_stock_position(conn, "ITM-INVCTL")
    assert result["item_id"] == "ITM-INVCTL"
    assert result["total_on_hand"] == 10
    assert result["total_in_transit"] == 8


def test_get_stock_position_unknown_item_raises(conn):
    with pytest.raises(ValueError):
        get_stock_position(conn, "ITM-NOPE")


def test_get_project_schedule(conn):
    result = get_project_schedule(conn, "PRJ-BHADLA2")
    assert result["project_id"] == "PRJ-BHADLA2"
    assert any(m["item_id"] == "ITM-INVCTL" for m in result["milestones"])


def test_get_contract_context(conn):
    result = get_contract_context(conn, "PRJ-BHADLA2")
    assert "force-majeure" in result["contract_notes_text"].lower()


def test_get_supplier_options(conn):
    result = get_supplier_options(conn, "ITM-MOD540")
    supplier_ids = {s["supplier_id"] for s in result["suppliers"]}
    assert {"SUP-BHARAT", "SUP-NORTH"}.issubset(supplier_ids)


def test_compute_reorder_point_shape(conn):
    result = compute_reorder_point(conn, "ITM-MOD540")
    assert result["item_id"] == "ITM-MOD540"
    assert "reorder_point" in result
    assert "eoq" in result
    assert "should_reorder" in result


def test_compute_priority_scores_scenario_1_ties(conn):
    result = compute_priority_scores(conn, ["PRJ-BHADLA2", "PRJ-PAVAGADA"], "ITM-INVCTL")
    assert result["scores"]["PRJ-BHADLA2"] == result["scores"]["PRJ-PAVAGADA"]
    assert set(result["ranking"]) == {"PRJ-BHADLA2", "PRJ-PAVAGADA"}


def test_draft_purchase_order_writes_undrafted_row(conn):
    result = draft_purchase_order(
        conn, item_id="ITM-MOD540", qty=5000, supplier_id="SUP-BHARAT", llm_reasoning_text="test reasoning"
    )
    row = conn.execute(
        "SELECT * FROM agent_recommendations WHERE id = ?", (result["recommendation_id"],)
    ).fetchone()
    assert row["type"] == "reorder"
    assert row["item_id"] == "ITM-MOD540"
    assert row["final_decision"] is None  # not yet approved/edited/rejected by a human
    formula_output = json.loads(row["formula_output_json"])
    assert formula_output["qty"] == 5000
    assert formula_output["supplier_id"] == "SUP-BHARAT"


def test_draft_allocation_plan_writes_undrafted_row(conn):
    result = draft_allocation_plan(
        conn,
        item_id="ITM-INVCTL",
        allocations={"PRJ-BHADLA2": 15, "PRJ-PAVAGADA": 9},
        llm_reasoning_text="test reasoning",
    )
    row = conn.execute(
        "SELECT * FROM agent_recommendations WHERE id = ?", (result["recommendation_id"],)
    ).fetchone()
    assert row["type"] == "allocation"
    assert row["final_decision"] is None
    assert json.loads(row["project_ids"]) == ["PRJ-BHADLA2", "PRJ-PAVAGADA"]


def test_tool_schemas_and_functions_match():
    schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
    function_names = set(TOOL_FUNCTIONS.keys())
    assert schema_names == function_names
