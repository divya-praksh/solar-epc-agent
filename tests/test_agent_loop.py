"""Tests for the reorder-mode agent loop with a mocked Anthropic client --
no network calls, no API key required. Verifies loop mechanics (message
construction, tool dispatch, termination) rather than LLM reasoning quality,
which can only be judged against the real API.
"""

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent.agent_loop import MAX_TOOL_ITERATIONS, REORDER_TOOL_NAMES, run_reorder_agent
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
