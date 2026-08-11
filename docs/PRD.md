# Solar EPC Reorder & Allocation Agent — PRD v2 (Buildable Scope)

**Divya Prakash · Rewrite, August 2026**
**Status: this version is scoped to actually be built as a working demo, not to read as a strategy deck.**

---

## 0. What changed from v1, and why

The first version described six agents, most of which turned out to be deterministic if/then logic with an LLM narrating over the top — that's not agentic, it's a rules engine with better copy. It also had no coordination between agents, unlabeled illustrative financials, and metric targets with no derivation.

This version cuts to **one agent**, built end-to-end with real tool-calling and a concrete case where the LLM's judgment changes the recommendation a pure formula would have made. Everything else from v1 (dispatch, exception detection, consumption analysis) is named as future scope, not built, and not claimed as built.

---

## 1. Problem (scoped, labeled)

Two decisions recur constantly in EPC inventory operations and are currently made reactively, by memory, or by whoever escalates loudest:

1. **Reorder timing** — when to reorder an item before it causes a site delay, and how much.
2. **Allocation under conflict** — when two projects need the same limited stock, which one gets it and why.

Both decisions depend on the same three inputs: stock position, project schedule, and project commercial risk. Today (per the internship this is based on) those three data sources exist but nobody is continuously cross-referencing them — a human has to think to check.

Financial figures like COD penalty clauses (typically 0.1–0.5% of contract value/day, per standard EPC contract structures) are used below **as illustrative scenario inputs for the demo, not as measured outcomes of a system that doesn't exist yet.** No metric in this doc is a validated baseline — Section 8 defines demo-level success criteria instead of enterprise KPIs.

---

## 2. What's actually being built (v1 scope)

**One agent: the Reorder & Allocation Agent.**

It does two things, both triggered by the same underlying signal (a stock position check against schedule):

- **Reorder mode**: stock for an item is projected to run short before its next milestone at *any* project → compute reorder point/quantity deterministically, then have the LLM produce a reasoned recommendation (supplier choice, urgency framing, risk note) and draft a PO for human approval.
- **Allocation mode**: available stock can't cover two or more competing project reservations → the LLM reasons over a starting weighted score *plus* unstructured context (contract terms, schedule notes) that the score can't see, and produces a ranked allocation with an explicit account of what each losing project gives up.

**Explicitly out of scope for this build**: dispatch planning, QC/exception escalation, consumption variance analysis, MCP protocol integration, multi-agent coordination, real ERP/PM system connections. These are named in Section 9 as "what v3 would add," not built now. This is the single biggest departure from v1: it stops claiming coverage it doesn't have.

---

## 3. Why this needs an LLM (the part v1 never proved)

A pure weighted formula for allocation looks like:

```
priority_score = w1*days_to_deadline + w2*revenue_at_risk + w3*penalty_exposure + w4*delay_probability
```

This is Level-1 automation — it can rank, but it can't see anything the weights weren't told to look for. The demo needs to show a case where that fails and an LLM reading unstructured input catches it. Concrete scripted scenario for the build:

> Project A and Project B are tied on `priority_score` for a shared batch of inverters. Project A's contract (fed to the agent as a short text excerpt, not a structured field) has a force-majeure clause that caps penalty exposure if the delay is supplier-caused. Project B's does not. A pure score treats them as equal. The agent, given both the score *and* the contract excerpt as context, should down-rank A's urgency and explain why in its recommendation.

This is the one seam in the whole system where "agent" is earned rather than asserted. The build must include this scenario as a test case, with the deterministic score and the LLM's adjusted reasoning shown side by side in the UI — that side-by-side view *is* the demo's thesis.

Reorder mode's equivalent seam: two suppliers have identical lead time and price, but one has a note field like "last 2 shipments arrived 5 days late" — the LLM should weigh that against a supplier ranking a formula alone would call a tie.

---

## 4. Architecture

```
SQLite (mock ERP/PM data)  -->  Deterministic compute layer (Python)  -->  Claude (tool use, reasoning layer)
   stock, BOM, schedule,        reorder point, EOQ, priority score          reads score + unstructured context
   contracts, supplier notes                                                produces reasoning + recommendation
                                                                                       |
                                                                                       v
                                                                    HITL approval UI (Streamlit)
                                                                    shows score vs. LLM adjustment
                                                                    approve / edit / reject
                                                                                       |
                                                                                       v
                                                                    SQLite write-back
                                                                    (PO drafted, allocation logged)
```

Numbers (reorder point, EOQ, priority score) are always computed in Python before the LLM ever sees them: **the LLM never generates a number, it reasons about numbers it's given.**

---

## 5. Data model (SQLite, mock data)

```sql
CREATE TABLE items (item_id, name, category, unit);
CREATE TABLE stock (item_id, warehouse_id, qty_on_hand, qty_reserved, qty_in_transit);
CREATE TABLE projects (project_id, name, cod_deadline, contract_value, contract_notes_text);
CREATE TABLE bom (project_id, item_id, qty_required, milestone_date);
CREATE TABLE suppliers (supplier_id, item_id, lead_time_days, unit_price, notes_text);
CREATE TABLE reservations (project_id, item_id, qty_reserved, priority_inputs_json);
CREATE TABLE agent_recommendations (id, type, item_id, project_ids, formula_output_json,
                                     llm_reasoning_text, final_decision, human_actor, timestamp);
```

`contract_notes_text` and supplier `notes_text` are the unstructured fields that make the LLM's job real instead of decorative — without them, this reduces back to a formula with extra steps.

A synthetic data generator script creates ~15 items, 5 projects, 3–4 suppliers per item, and a handful of scripted conflict scenarios (including the force-majeure case from Section 3) so the demo is repeatable and explainable in an interview.

---

## 6. Tools (Claude tool-use definitions)

| Tool | Purpose | Access |
|---|---|---|
| `get_stock_position(item_id)` | current, reserved, in-transit stock | Read |
| `get_project_schedule(project_id)` | milestones, deadlines | Read |
| `get_contract_context(project_id)` | raw contract notes text | Read |
| `get_supplier_options(item_id)` | lead time, price, notes | Read |
| `compute_reorder_point(item_id)` | deterministic Python function, called as a tool | Read (compute) |
| `compute_priority_scores(project_ids, item_id)` | deterministic Python function | Read (compute) |
| `draft_purchase_order(item_id, qty, supplier_id)` | writes a draft row, not submitted | Write (draft only) |
| `draft_allocation_plan(item_id, allocations)` | writes a draft row, not submitted | Write (draft only) |

No tool submits a PO or commits an allocation without a human clicking approve in the UI.

---

## 7. Human-in-the-loop UI (minimum viable)

A single-page Streamlit app with two views:

- **Recommendation queue**: each pending recommendation shows the deterministic score, the LLM's reasoning text, and a clear diff when the LLM's suggested action differs from what the raw score alone would produce.
- **Decision action**: approve as-is / edit quantity or ranking / reject, with a required one-line reason on edit or reject — this reason gets logged.

---

## 8. Success criteria for the demo (not enterprise KPIs)

- The scripted force-majeure and stale-supplier scenarios produce a visibly different recommendation than the raw formula score, with a legible reason — this is the core proof point.
- Every numeric value shown (reorder qty, EOQ, priority score) is traceable to the deterministic layer, never to LLM output — verified by a test that asserts recommendation JSON numbers match the compute-layer output.
- A human can approve, edit, or reject any recommendation, and rejections/edits are logged with a reason.
- The system runs end-to-end on mock data with no manual data massaging during the demo.

---

## 9. Explicitly deferred (not built, not claimed)

Dispatch planning agent, QC/exception escalation agent, consumption variance agent, multi-agent coordination/conflict resolution between agents, MCP protocol integration, real ERP/PM system connectors, alert-fatigue tuning at scale, cost/latency budgeting for continuous monitoring in production.

---

## 10. Build plan (solo, portfolio timeline)

See `docs/BUILD_PLAN.md` for the day-by-day breakdown and running log.

---

## 11. Risks specific to building this

| Risk | Mitigation |
|---|---|
| LLM reasoning ends up agreeing with the formula every time — no visible seam | Design scenarios where a formula-blind fact (contract clause, stale note) directly changes the correct answer, not just phrasing |
| Demo reads as toy due to synthetic data | Keep numbers and contract language realistic (grounded in internship domain knowledge), and be upfront in the write-up that data is synthetic and why |
| Scope creep back toward six agents mid-build | This PRD is the scope; anything not in Section 2 goes in Section 9, not into the build |
