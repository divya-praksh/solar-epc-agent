"""Tests for the reorder-mode and allocation-mode agent loops with a mocked
Anthropic client -- no network calls, no API key required. Verifies loop
mechanics (message construction, tool dispatch, termination) rather than
LLM reasoning quality, which can only be judged against the real API.
"""

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.agent_loop import (
    ALLOCATION_TOOL_NAMES,
    MAX_TOOL_ITERATIONS,
    REORDER_TOOL_NAMES,
    run_allocation_agent,
    run_reorder_agent,
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


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(id_, name, tool_input):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=tool_input)


def _message(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_agent_investigates_then_drafts_po(mock_anthropic_cls, conn):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    investigate_call = _tool_use_block("t1", "compute_reorder_point", {"item_id": "ITM-MOD540"})
    draft_call = _tool_use_block(
        "t2",
        "draft_purchase_order",
        {
            "item_id": "ITM-MOD540",
            "qty": 6000,
            "supplier_id": "SUP-BHARAT",
            "llm_reasoning_text": "SUP-BHARAT has a clean delivery record at the same price/lead time as SUP-NORTH.",
        },
    )
    final = _text_block("Drafted a PO for ITM-MOD540 from SUP-BHARAT.")

    mock_client.messages.create.side_effect = [
        _message([investigate_call], "tool_use"),
        _message([draft_call], "tool_use"),
        _message([final], "end_turn"),
    ]

    result = run_reorder_agent(conn, "ITM-MOD540")

    assert result["drafted"] is not None
    assert result["drafted"]["status"] == "drafted"
    assert "Drafted a PO" in result["final_text"]
    assert mock_client.messages.create.call_count == 3

    row = conn.execute(
        "SELECT * FROM agent_recommendations WHERE id = ?", (result["drafted"]["recommendation_id"],)
    ).fetchone()
    assert row["type"] == "reorder"
    assert row["item_id"] == "ITM-MOD540"


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_agent_can_decide_no_reorder_needed(mock_anthropic_cls, conn):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    final = _text_block("Stock is well above the reorder point; no action needed.")
    mock_client.messages.create.side_effect = [_message([final], "end_turn")]

    result = run_reorder_agent(conn, "ITM-MOD540")

    assert result["drafted"] is None
    assert "no action needed" in result["final_text"]


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_agent_stops_after_max_tool_iterations(mock_anthropic_cls, conn):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    looping_call = _tool_use_block("t1", "get_stock_position", {"item_id": "ITM-MOD540"})
    mock_client.messages.create.side_effect = [_message([looping_call], "tool_use")] * MAX_TOOL_ITERATIONS

    result = run_reorder_agent(conn, "ITM-MOD540")

    assert result["drafted"] is None
    assert "max tool iterations" in result["final_text"]
    assert mock_client.messages.create.call_count == MAX_TOOL_ITERATIONS


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_only_reorder_tools_are_exposed(mock_anthropic_cls, conn):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_message([_text_block("noop")], "end_turn")]

    run_reorder_agent(conn, "ITM-MOD540")

    _, kwargs = mock_client.messages.create.call_args
    exposed_names = {tool["name"] for tool in kwargs["tools"]}
    assert exposed_names == REORDER_TOOL_NAMES
    assert "draft_allocation_plan" not in exposed_names
    assert "get_contract_context" not in exposed_names


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_allocation_agent_investigates_then_drafts_plan(mock_anthropic_cls, conn):
    """Grounded in Scenario 1: PRJ-BHADLA2 and PRJ-PAVAGADA tie on
    compute_priority_scores for ITM-INVCTL, so a correct allocation
    down-ranking BHADLA2's urgency can only come from contract context."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    score_call = _tool_use_block(
        "t1", "compute_priority_scores", {"project_ids": ["PRJ-BHADLA2", "PRJ-PAVAGADA"], "item_id": "ITM-INVCTL"}
    )
    contract_call = _tool_use_block("t2", "get_contract_context", {"project_id": "PRJ-BHADLA2"})
    draft_call = _tool_use_block(
        "t3",
        "draft_allocation_plan",
        {
            "item_id": "ITM-INVCTL",
            "allocations": {"PRJ-BHADLA2": 8, "PRJ-PAVAGADA": 9},
            "llm_reasoning_text": (
                "Scores tie, but PRJ-BHADLA2's force-majeure clause caps its penalty "
                "exposure for supplier-caused delay, so PAVAGADA gets priority."
            ),
        },
    )
    final = _text_block("Drafted an allocation favoring PRJ-PAVAGADA despite the tied score.")

    mock_client.messages.create.side_effect = [
        _message([score_call], "tool_use"),
        _message([contract_call], "tool_use"),
        _message([draft_call], "tool_use"),
        _message([final], "end_turn"),
    ]

    result = run_allocation_agent(conn, ["PRJ-BHADLA2", "PRJ-PAVAGADA"], "ITM-INVCTL")

    assert result["drafted"] is not None
    assert result["drafted"]["status"] == "drafted"
    assert "favoring PRJ-PAVAGADA" in result["final_text"]

    row = conn.execute(
        "SELECT * FROM agent_recommendations WHERE id = ?", (result["drafted"]["recommendation_id"],)
    ).fetchone()
    assert row["type"] == "allocation"
    assert json.loads(row["project_ids"]) == ["PRJ-BHADLA2", "PRJ-PAVAGADA"]


@patch("src.agent.agent_loop.anthropic.Anthropic")
def test_only_allocation_tools_are_exposed(mock_anthropic_cls, conn):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.side_effect = [_message([_text_block("noop")], "end_turn")]

    run_allocation_agent(conn, ["PRJ-BHADLA2", "PRJ-PAVAGADA"], "ITM-INVCTL")

    _, kwargs = mock_client.messages.create.call_args
    exposed_names = {tool["name"] for tool in kwargs["tools"]}
    assert exposed_names == ALLOCATION_TOOL_NAMES
    assert "draft_purchase_order" not in exposed_names
    assert "get_supplier_options" not in exposed_names
