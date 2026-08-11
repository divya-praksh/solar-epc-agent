# Solar EPC Reorder & Allocation Agent

A single, real, tool-calling agent for Solar EPC inventory decisions: when to reorder
an item before it causes a site delay, and how to allocate scarce stock across
competing projects when a formula alone can't see the full picture.

This is the buildable rewrite of a larger 6-agent PRD. Scope was deliberately cut to
one agent so the core claim — that an LLM's reasoning changes the outcome, not just
the wording — can actually be demonstrated end to end. See `docs/PRD.md` for the
full design rationale and `docs/BUILD_PLAN.md` for the day-by-day build log.

## Why this exists

Every number the agent shows (reorder quantity, EOQ, priority score) is computed
deterministically in Python — never by the LLM. The LLM's only job is to reason over
unstructured context (contract notes, supplier reliability notes) that the formula
can't see, and to produce a recommendation a human then approves, edits, or rejects.
Nothing is written to the database without a human clicking approve.

## Project layout

```
src/
  db/        SQLite schema, connection helper, synthetic data generator
  compute/   Deterministic reorder point / EOQ / priority score functions
  agent/     Claude tool-use loop and tool definitions
  ui/        Streamlit human-in-the-loop approval interface
tests/       Unit tests for the compute layer and agent tool wiring
docs/        PRD and the day-by-day build plan
data/        SQLite db file lives here at runtime (gitignored)
```

## Status

Day-by-day progress is tracked in `docs/BUILD_PLAN.md`. Each day's work lands as its
own commit with a message describing what shipped.

## Setup (once code lands)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your ANTHROPIC_API_KEY
python -m src.db.seed_data   # builds data/inventory.db
streamlit run src/ui/app.py
```
