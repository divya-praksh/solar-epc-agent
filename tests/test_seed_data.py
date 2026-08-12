"""Sanity checks on the seeded database: FK integrity, no orphan rows, and
that the two scripted conflict scenarios from PRD Section 3 (see
src/db/seed_data.py) are actually present with the values the demo depends on.
"""

import json
import sqlite3
from pathlib import Path

import pytest

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


def test_no_orphan_foreign_keys(conn):
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_expected_row_counts(conn):
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("items", "projects", "stock", "bom")
    }
    assert counts["items"] == 15
    assert counts["projects"] == 5
    assert counts["stock"] == 15
    assert counts["bom"] > 0


def test_every_item_has_at_least_three_suppliers(conn):
    rows = conn.execute(
        "SELECT item_id, COUNT(*) AS n FROM suppliers GROUP BY item_id"
    ).fetchall()
    short = [r["item_id"] for r in rows if r["n"] < 3]
    assert short == [], f"items with fewer than 3 suppliers: {short}"
    assert len(rows) == 15, "every item should have at least one supplier row"


def test_every_bom_item_exists_in_items(conn):
    orphans = conn.execute(
        "SELECT bom.item_id FROM bom LEFT JOIN items USING (item_id) WHERE items.item_id IS NULL"
    ).fetchall()
    assert orphans == []


def test_scenario_1_force_majeure_allocation_tie(conn):
    """PRD Section 3: PRJ-BHADLA2 vs PRJ-PAVAGADA tie on ITM-INVCTL priority
    inputs and BOM milestone date, so only contract_notes_text should
    distinguish them."""
    reservations = conn.execute(
        "SELECT project_id, qty_reserved, priority_inputs_json FROM reservations "
        "WHERE item_id = 'ITM-INVCTL' AND project_id IN ('PRJ-BHADLA2', 'PRJ-PAVAGADA') "
        "ORDER BY project_id"
    ).fetchall()
    assert len(reservations) == 2

    inputs = [json.loads(r["priority_inputs_json"]) for r in reservations]
    assert inputs[0] == inputs[1], "scenario requires tied priority inputs"

    milestones = conn.execute(
        "SELECT DISTINCT milestone_date FROM bom "
        "WHERE item_id = 'ITM-INVCTL' AND project_id IN ('PRJ-BHADLA2', 'PRJ-PAVAGADA')"
    ).fetchall()
    assert len(milestones) == 1, "scenario requires the same milestone date"

    total_qty = sum(r["qty_reserved"] for r in reservations)
    stock = conn.execute(
        "SELECT qty_on_hand, qty_in_transit FROM stock WHERE item_id = 'ITM-INVCTL'"
    ).fetchone()
    available = stock["qty_on_hand"] + stock["qty_in_transit"]
    assert available < total_qty, "scenario requires a real shortage to force an allocation decision"

    notes = {
        r["project_id"]: r["contract_notes_text"]
        for r in conn.execute(
            "SELECT project_id, contract_notes_text FROM projects "
            "WHERE project_id IN ('PRJ-BHADLA2', 'PRJ-PAVAGADA')"
        ).fetchall()
    }
    assert "capped at" in notes["PRJ-BHADLA2"].lower()
    assert "uncapped" in notes["PRJ-PAVAGADA"].lower()


def test_scenario_2_stale_supplier_reorder_tie(conn):
    """PRD Section 3: SUP-BHARAT and SUP-NORTH tie on lead time and price for
    ITM-MOD540, so only notes_text should distinguish them."""
    suppliers = {
        r["supplier_id"]: r
        for r in conn.execute(
            "SELECT supplier_id, lead_time_days, unit_price, notes_text FROM suppliers "
            "WHERE item_id = 'ITM-MOD540' AND supplier_id IN ('SUP-BHARAT', 'SUP-NORTH')"
        ).fetchall()
    }
    assert set(suppliers) == {"SUP-BHARAT", "SUP-NORTH"}
    assert suppliers["SUP-BHARAT"]["lead_time_days"] == suppliers["SUP-NORTH"]["lead_time_days"]
    assert suppliers["SUP-BHARAT"]["unit_price"] == suppliers["SUP-NORTH"]["unit_price"]
    assert "late" in suppliers["SUP-NORTH"]["notes_text"].lower()
    assert "late" not in suppliers["SUP-BHARAT"]["notes_text"].lower()


def test_reseeding_is_idempotent(conn):
    before = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("items", "projects", "bom", "suppliers", "stock", "reservations")
    }
    seed(conn)
    after = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("items", "projects", "bom", "suppliers", "stock", "reservations")
    }
    assert before == after
