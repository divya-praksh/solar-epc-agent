-- Solar EPC Reorder & Allocation Agent — SQLite schema
-- See docs/PRD.md Section 5 for the data model rationale.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS items (
    item_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock (
    item_id         TEXT NOT NULL REFERENCES items(item_id),
    warehouse_id    TEXT NOT NULL,
    qty_on_hand     INTEGER NOT NULL DEFAULT 0,
    qty_reserved    INTEGER NOT NULL DEFAULT 0,
    qty_in_transit  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (item_id, warehouse_id)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id          TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    cod_deadline         TEXT NOT NULL,        -- ISO date
    contract_value       REAL NOT NULL,
    contract_notes_text  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bom (
    project_id      TEXT NOT NULL REFERENCES projects(project_id),
    item_id         TEXT NOT NULL REFERENCES items(item_id),
    qty_required    INTEGER NOT NULL,
    milestone_date  TEXT NOT NULL,             -- ISO date
    PRIMARY KEY (project_id, item_id)
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id     TEXT NOT NULL,
    item_id         TEXT NOT NULL REFERENCES items(item_id),
    lead_time_days  INTEGER NOT NULL,
    unit_price      REAL NOT NULL,
    notes_text      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (supplier_id, item_id)
);

CREATE TABLE IF NOT EXISTS reservations (
    project_id           TEXT NOT NULL REFERENCES projects(project_id),
    item_id              TEXT NOT NULL REFERENCES items(item_id),
    qty_reserved         INTEGER NOT NULL,
    priority_inputs_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (project_id, item_id)
);

CREATE TABLE IF NOT EXISTS agent_recommendations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    type                TEXT NOT NULL CHECK (type IN ('reorder', 'allocation')),
    item_id             TEXT NOT NULL REFERENCES items(item_id),
    project_ids         TEXT NOT NULL DEFAULT '[]',   -- JSON array
    formula_output_json TEXT NOT NULL,
    llm_reasoning_text  TEXT NOT NULL,
    final_decision      TEXT,                          -- NULL until human acts: approved/edited/rejected
    human_actor         TEXT,
    timestamp           TEXT NOT NULL DEFAULT (datetime('now'))
);
