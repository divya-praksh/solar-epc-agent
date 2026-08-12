# Day-by-day build plan

25 working days across 5 weeks, matching the PRD's build plan section but broken
down to daily granularity. Each day should end in one commit (or a small handful of
logically separate commits) with a message describing what actually shipped — not
"wip" or "updates". If a day's work doesn't compile/pass its tests, don't push it;
fix it first or split the commit so `main` always stays in a working state.

Git discipline for this project:
- One feature/day of work per commit where possible. If a day naturally splits into
  two independent pieces, make two commits.
- Commit message format: `Day N: <what shipped>` — e.g. `Day 3: synthetic data generator for items and suppliers`.
- Never commit `data/*.db`, `.env`, or `__pycache__` — already covered by `.gitignore`, but check `git status` before every commit.
- Run `pytest` before committing anything that touches `src/compute` or `src/agent` — those are the two places correctness actually matters.
- Push to `main` directly is fine for a solo project at this scale; no need for branches/PRs unless you want the practice.

Progress log: check off each day here as you finish it, with the date and commit hash.

---

## Week 1 — Data foundation

- [ ] **Day 1** — Repo scaffold (this delivery): folder structure, README, `.gitignore`, `requirements.txt`, `.env.example`, PRD + build plan docs. Commit: `Day 1: project scaffold, README, PRD, build plan`.
- [x] **Day 2** — SQLite schema (`src/db/schema.sql`) for items, stock, projects, bom, suppliers, reservations, agent_recommendations. Connection helper (`src/db/connection.py`) that creates the db from schema if it doesn't exist.
- [x] **Day 3** — Synthetic data generator (`src/db/seed_data.py`): ~15 items, 5 projects, 3–4 suppliers per item, realistic contract/supplier notes text.
- [ ] **Day 4** — Scripted conflict scenarios: hand-write the force-majeure allocation tie and the stale-supplier reorder tie from PRD Section 3 directly into the seed data so they're reproducible, not random.
- [ ] **Day 5** — Data validation: a small script/test that sanity-checks the seeded db (foreign keys resolve, no orphan rows, scenario rows present). Review week 1 against the PRD data model.

## Week 2 — Deterministic compute layer

- [ ] **Day 6** — `src/compute/reorder.py`: reorder point and EOQ functions, pure functions taking plain values (no db access inside compute functions — keep it testable).
- [ ] **Day 7** — `src/compute/priority_score.py`: the weighted priority score function from PRD Section 3.
- [ ] **Day 8** — `tests/test_compute.py`: unit tests for both, including the exact numbers from the two scripted scenarios so there's a known-good baseline.
- [ ] **Day 9** — Small CLI script (`src/compute/__main__.py` or similar) that prints reorder points and priority scores for the seeded data — lets you sanity check compute output before wiring in the LLM.
- [ ] **Day 10** — Refactor pass + review: make sure compute layer has zero LLM dependency and is fully covered by tests.

## Week 3 — Agent loop

- [ ] **Day 11** — `src/agent/tools.py`: tool definitions matching PRD Section 6 (get_stock_position, get_project_schedule, get_contract_context, get_supplier_options, compute_reorder_point, compute_priority_scores, draft_purchase_order, draft_allocation_plan).
- [ ] **Day 12** — `src/agent/agent_loop.py`: reorder-mode loop — Claude tool-use call, agent reads stock/schedule/supplier tools, calls compute_reorder_point, produces reasoning + draft PO.
- [ ] **Day 13** — Allocation-mode loop: same file, second entry point — agent reads contract context + compute_priority_scores, produces ranked allocation with reasoning.
- [ ] **Day 14** — Wire the scripted scenarios (force-majeure, stale supplier) through the real agent loop end to end via a CLI script; confirm the LLM's output actually diverges from the raw score as designed.
- [ ] **Day 15** — Save every recommendation (formula output + LLM reasoning text) into `agent_recommendations`; write a test asserting the numeric fields in a saved recommendation match the compute layer's output exactly (PRD success criterion).

## Week 4 — HITL UI

- [ ] **Day 16** — Streamlit scaffold (`src/ui/app.py`): page shell, db connection, run-agent trigger button.
- [ ] **Day 17** — Recommendation queue view: list pending recommendations with formula score and LLM reasoning shown side by side.
- [ ] **Day 18** — Decision action: approve / edit / reject buttons, required reason field on edit/reject, writes back to `agent_recommendations` and (on approve) marks the draft PO/allocation as committed.
- [ ] **Day 19** — Diff view: explicit visual callout when the LLM's recommendation differs from what the raw formula alone would have produced — this is the demo's central UI moment per PRD Section 3.
- [ ] **Day 20** — UI polish pass, click through both scripted scenarios end to end in the browser, fix anything broken.

## Week 5 — Demo & writeup

- [ ] **Day 21** — Full end-to-end run of both scripted scenarios from a clean seeded db, screenshots/recording of the diff view.
- [ ] **Day 22** — Bug fixes from Day 21's run; make sure `pytest` is green and the app boots cleanly from a fresh clone.
- [ ] **Day 23** — Write-up: short case study doc pairing the PRD's thesis ("this is where the LLM's judgment earns its place") with the actual screenshots/output from the build.
- [ ] **Day 24** — Record a short demo walkthrough (screen recording) for the portfolio.
- [ ] **Day 25** — Final polish, tag a `v1.0` release/commit, update README status section.
