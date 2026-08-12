"""Synthetic data generator for the Solar EPC demo.

Hand-crafted, not randomized: the numbers here are fixed so the demo is
reproducible and explainable end to end. Run with `python -m src.db.seed_data`.

Company names are fictional archetypes (reliable / average / budget-and-slow
supplier personas), not real vendors.

Two scripted conflict scenarios (PRD Section 3) are baked directly into this
data so they reproduce identically on every seed run:

SCENARIO 1 — force-majeure allocation tie (ITM-INVCTL, PRJ-BHADLA2 vs
PRJ-PAVAGADA): both projects' reservations carry an identical
priority_inputs_json and an identical BOM milestone_date, so a pure weighted
score ties them regardless of the weights chosen in compute/priority_score.py.
Only their contract_notes_text differs — BHADLA2 has a force-majeure carve-out
capping penalty exposure for supplier-caused delay, PAVAGADA does not. Stock
is deliberately short of combined demand, forcing an allocation decision.

SCENARIO 2 — stale-supplier reorder tie (ITM-MOD540, SUP-BHARAT vs
SUP-NORTH): both suppliers are priced and lead-timed identically, so a pure
formula can't break the tie. SUP-NORTH's notes_text flags two late shipments;
SUP-BHARAT's does not.
"""

from src.db.connection import get_connection

ITEMS = [
    # item_id,      name,                          category,     unit
    ("ITM-MOD540", "Solar Module 540Wp",            "module",      "nos"),
    ("ITM-INVSTR", "String Inverter 100kW",          "inverter",    "nos"),
    ("ITM-INVCTL", "Central Inverter 3.3MW",         "inverter",    "nos"),
    ("ITM-MC4",    "MC4 Connector Pair",             "connector",   "pair"),
    ("ITM-DCC4",   "DC Cable 4 sq mm",               "cable",       "meter"),
    ("ITM-DCC6",   "DC Cable 6 sq mm",               "cable",       "meter"),
    ("ITM-ACC300", "AC Cable 3.5Cx300 sq mm",        "cable",       "meter"),
    ("ITM-MMS",    "Module Mounting Structure",      "structure",   "set"),
    ("ITM-SCB12",  "Solar Combiner Box 12-in-1",     "electrical",  "nos"),
    ("ITM-EARTH",  "Earthing Strip GI 25x3mm",       "electrical",  "meter"),
    ("ITM-LA",     "Lightning Arrestor",             "electrical",  "nos"),
    ("ITM-JB",     "Junction Box IP65",              "electrical",  "nos"),
    ("ITM-ACDB",   "AC Distribution Board",          "electrical",  "nos"),
    ("ITM-XFMR",   "Power Transformer 33kV",         "transformer", "nos"),
    ("ITM-HTC",    "HT Cable 33kV XLPE",             "cable",       "meter"),
]

PROJECTS = [
    # project_id,       name,                                          cod_deadline,  contract_value, contract_notes_text
    ("PRJ-BHADLA2", "Bhadla Solar Park Phase 2 (50MW)", "2026-11-15", 1_850_000_000,
     "EPC contract includes a force-majeure carve-out (Clause 14.3): liquidated "
     "damages for COD delay are capped at 2% of contract value if the delay is "
     "demonstrably caused by supplier non-delivery rather than contractor default. "
     "Standard LD rate otherwise is 0.3% of contract value per day of delay."),
    ("PRJ-PAVAGADA", "Pavagada Solar Farm Extension (30MW)", "2026-11-20", 1_100_000_000,
     "Standard EPC terms. Liquidated damages for COD delay: 0.3% of contract value "
     "per day, uncapped, regardless of cause. No force-majeure carve-out for "
     "sub-vendor delays — client legal declined to include one during negotiation."),
    ("PRJ-RAJCANAL", "Rajasthan Canal-Top Solar (20MW)", "2026-10-05", 780_000_000,
     "Canal-top mounting adds a structural inspection gate before energization; "
     "LD rate 0.25% of contract value per day past COD. Client has flagged this "
     "as a reference project for future canal-top bids, so schedule slippage "
     "carries reputational weight beyond the contract penalty."),
    ("PRJ-TNROOFTOP", "Tamil Nadu Rooftop Cluster (15MW)", "2026-09-25", 540_000_000,
     "Multi-site rooftop rollout across 40 commercial roofs. Tightest schedule of "
     "the current portfolio — COD is only weeks out. LD rate 0.4% of contract "
     "value per day, plus a per-site late fee if individual roofs miss their "
     "energization window."),
    ("PRJ-GUJHYBRID", "Gujarat Hybrid Solar-Wind (40MW)", "2026-12-10", 1_420_000_000,
     "Hybrid site sharing grid interconnection with an existing wind asset. LD "
     "rate 0.3% of contract value per day. Interconnection slot is booked with "
     "the DISCOM for early December; missing it risks a multi-month requeue "
     "independent of the contractual penalty."),
]

# project_id, item_id, qty_required, milestone_date
BOM = [
    ("PRJ-BHADLA2", "ITM-MOD540", 92600, "2026-09-30"),
    ("PRJ-BHADLA2", "ITM-INVCTL", 15,    "2026-10-10"),  # SCENARIO 1: milestone matches PAVAGADA below
    ("PRJ-BHADLA2", "ITM-MMS",    500,   "2026-09-15"),
    ("PRJ-BHADLA2", "ITM-DCC6",   25000, "2026-09-20"),
    ("PRJ-BHADLA2", "ITM-ACC300", 8000,  "2026-10-01"),
    ("PRJ-BHADLA2", "ITM-SCB12",  40,    "2026-09-25"),
    ("PRJ-BHADLA2", "ITM-XFMR",   2,     "2026-10-20"),
    ("PRJ-BHADLA2", "ITM-HTC",    3000,  "2026-10-15"),
    ("PRJ-BHADLA2", "ITM-EARTH",  12000, "2026-09-10"),

    ("PRJ-PAVAGADA", "ITM-MOD540", 55600, "2026-10-01"),
    ("PRJ-PAVAGADA", "ITM-INVCTL", 9,     "2026-10-10"),  # SCENARIO 1: milestone matches BHADLA2 above
    ("PRJ-PAVAGADA", "ITM-MMS",    300,   "2026-09-20"),
    ("PRJ-PAVAGADA", "ITM-DCC6",   15000, "2026-09-25"),
    ("PRJ-PAVAGADA", "ITM-SCB12",  24,    "2026-09-28"),
    ("PRJ-PAVAGADA", "ITM-XFMR",   1,     "2026-10-25"),
    ("PRJ-PAVAGADA", "ITM-EARTH",  7000,  "2026-09-12"),

    ("PRJ-RAJCANAL", "ITM-MOD540", 37000, "2026-09-10"),
    ("PRJ-RAJCANAL", "ITM-INVSTR", 200,   "2026-09-15"),
    ("PRJ-RAJCANAL", "ITM-MMS",    200,   "2026-08-25"),
    ("PRJ-RAJCANAL", "ITM-DCC4",   12000, "2026-08-30"),
    ("PRJ-RAJCANAL", "ITM-SCB12",  16,    "2026-09-05"),
    ("PRJ-RAJCANAL", "ITM-EARTH",  5000,  "2026-08-20"),

    ("PRJ-TNROOFTOP", "ITM-MOD540", 27800, "2026-08-25"),
    ("PRJ-TNROOFTOP", "ITM-INVSTR", 150,   "2026-08-28"),
    ("PRJ-TNROOFTOP", "ITM-MMS",    150,   "2026-08-18"),
    ("PRJ-TNROOFTOP", "ITM-MC4",    6000,  "2026-08-20"),
    ("PRJ-TNROOFTOP", "ITM-DCC4",   9000,  "2026-08-22"),
    ("PRJ-TNROOFTOP", "ITM-ACDB",   15,    "2026-09-01"),
    ("PRJ-TNROOFTOP", "ITM-JB",     150,   "2026-08-20"),

    ("PRJ-GUJHYBRID", "ITM-MOD540", 74000, "2026-10-20"),
    ("PRJ-GUJHYBRID", "ITM-INVCTL", 12,    "2026-11-01"),
    ("PRJ-GUJHYBRID", "ITM-MMS",    400,   "2026-10-05"),
    ("PRJ-GUJHYBRID", "ITM-DCC6",   20000, "2026-10-10"),
    ("PRJ-GUJHYBRID", "ITM-ACC300", 6000,  "2026-10-25"),
    ("PRJ-GUJHYBRID", "ITM-SCB12",  32,    "2026-10-08"),
    ("PRJ-GUJHYBRID", "ITM-XFMR",   2,     "2026-11-10"),
    ("PRJ-GUJHYBRID", "ITM-HTC",    2500,  "2026-11-05"),
    ("PRJ-GUJHYBRID", "ITM-LA",     20,    "2026-10-30"),
    ("PRJ-GUJHYBRID", "ITM-EARTH",  9000,  "2026-09-30"),
]

# supplier_id, item_id, lead_time_days, unit_price, notes_text
SUPPLIERS = [
    # Solar Module 540Wp
    ("SUP-SURYA",    "ITM-MOD540", 21, 10800,
     "Tier-1 cell supplier, consistent on-time delivery across the last 6 POs."),
    # SCENARIO 2: SUP-BHARAT and SUP-NORTH are tied on lead time (18d) and price
    # (9600) — a pure formula can't break this tie. The seam is in notes_text.
    ("SUP-BHARAT",   "ITM-MOD540", 18, 9600,
     "Mid-tier vendor, on-time across the last 4 orders, no adverse notes on file."),
    ("SUP-NORTH",    "ITM-MOD540", 18, 9600,
     "Cheapest lead time/price match to SUP-BHARAT. Last 2 shipments arrived 5 "
     "days late; no explanation given beyond 'logistics delay'."),
    ("SUP-SUNTECH",  "ITM-MOD540", 24, 11100,
     "Premium panel efficiency bin, used for space-constrained rooftop sites."),

    # String Inverter 100kW
    ("SUP-MERIDIAN", "ITM-INVSTR", 30, 495000,
     "Preferred inverter vendor for the last 3 projects, strong service response."),
    ("SUP-VEGA",      "ITM-INVSTR", 30, 478000,
     "Same lead time and price band as Meridian on paper; no adverse notes on file."),
    ("SUP-BHARAT",    "ITM-INVSTR", 35, 460000,
     "Budget option, longer lead time, acceptable for non-critical-path orders."),
    ("SUP-PRIME",     "ITM-INVSTR", 28, 505000,
     "Fastest lead time in this category, priced at a premium."),

    # Central Inverter 3.3MW
    ("SUP-MERIDIAN", "ITM-INVCTL", 45, 10200000,
     "Same vendor as string inverters; volume discount available above 10 units."),
    ("SUP-VEGA",      "ITM-INVCTL", 48, 9850000,
     "Slightly cheaper, one project delay reported in the last 12 months (client-side, not vendor-caused)."),
    ("SUP-STATFIELD", "ITM-INVCTL", 50, 9600000,
     "New vendor relationship, first order was on time."),

    # MC4 Connector Pair
    ("SUP-COASTAL", "ITM-MC4", 10, 42,
     "Standard connector supplier, no issues on file."),
    ("SUP-BHARAT",  "ITM-MC4", 12, 38,
     "Bulk order discount available above 5,000 pairs."),
    ("SUP-NORTH",   "ITM-MC4", 9,  35,
     "Cheapest, ships fast for small orders."),

    # DC Cable 4 sq mm
    ("SUP-RAJCABLE", "ITM-DCC4", 14, 32,
     "Consistent quality, used across most rooftop projects to date."),
    ("SUP-GANGA",    "ITM-DCC4", 15, 29,
     "Slightly cheaper, comparable lead time."),
    ("SUP-NORTH",    "ITM-DCC4", 12, 33,
     "Fastest turnaround, mid pricing."),

    # DC Cable 6 sq mm
    ("SUP-RAJCABLE", "ITM-DCC6", 16, 47,
     "Same vendor as DC 4sqmm, consistent quality."),
    ("SUP-GANGA",    "ITM-DCC6", 17, 44,
     "Marginally cheaper, one late delivery flagged in Q2."),
    ("SUP-BHARAT",   "ITM-DCC6", 15, 49,
     "Reliable but priced at the high end."),

    # AC Cable 3.5Cx300 sq mm
    ("SUP-RAJCABLE", "ITM-ACC300", 20, 1950,
     "Heavy-gauge cable, on-time for both prior large orders."),
    ("SUP-GANGA",    "ITM-ACC300", 22, 1880,
     "Cheaper, longer lead time for this gauge."),
    ("SUP-VIDYUT",   "ITM-ACC300", 25, 2050,
     "Bundled quote available when ordered with transformer/HT cable."),

    # Module Mounting Structure
    ("SUP-ANANT",  "ITM-MMS", 25, 7200,
     "Primary structural vendor, galvanization quality consistently good."),
    ("SUP-DECCAN", "ITM-MMS", 28, 6800,
     "Cheaper, but 2024 audit flagged inconsistent coating thickness on one batch."),
    ("SUP-NORTH",  "ITM-MMS", 22, 7500,
     "Fastest lead time, priced at a premium for this category."),

    # Solar Combiner Box 12-in-1
    ("SUP-DCOMBINE", "ITM-SCB12", 18, 21000,
     "Specialist electrical enclosure vendor, IP65-rated as standard."),
    ("SUP-BHARAT",   "ITM-SCB12", 20, 19500,
     "Cheaper, generic enclosure brand, acceptable for non-coastal sites."),
    ("SUP-MERIDIAN", "ITM-SCB12", 22, 22500,
     "Higher spec, sold as a bundle with inverter orders."),

    # Earthing Strip GI 25x3mm
    ("SUP-PRAKASH", "ITM-EARTH", 10, 98,
     "Standard safety-item vendor, no issues across 8 prior orders."),
    ("SUP-BHARAT",  "ITM-EARTH", 12, 92,
     "Cheaper, slightly longer lead time."),
    ("SUP-NORTH",   "ITM-EARTH", 9,  105,
     "Fastest, priced at a premium."),

    # Lightning Arrestor
    ("SUP-PRAKASH",   "ITM-LA", 15, 4100,
     "Same vendor as earthing systems, bundled discount available."),
    ("SUP-VIDYUT",    "ITM-LA", 18, 3900,
     "Cheaper, standard lead time for this category."),
    ("SUP-STATFIELD", "ITM-LA", 20, 4400,
     "Higher spec rating, used on prior hybrid-site projects."),

    # Junction Box IP65
    ("SUP-PRAKASH",  "ITM-JB", 10, 1450,
     "Reliable, consistent IP65 rating verification on delivery."),
    ("SUP-DCOMBINE", "ITM-JB", 12, 1350,
     "Cheaper, from the same vendor as combiner boxes."),
    ("SUP-BHARAT",   "ITM-JB", 11, 1500,
     "Slightly pricier, fastest of the three for small orders."),

    # AC Distribution Board
    ("SUP-STATFIELD", "ITM-ACDB", 20, 52000,
     "Standard vendor for rooftop-scale ACDBs."),
    ("SUP-DCOMBINE",  "ITM-ACDB", 22, 49500,
     "Cheaper, comparable spec."),
    ("SUP-BHARAT",    "ITM-ACDB", 18, 55000,
     "Fastest lead time, priced at a premium."),

    # Power Transformer 33kV
    ("SUP-VIDYUT",    "ITM-XFMR", 60, 3450000,
     "Primary transformer vendor across the current project portfolio."),
    ("SUP-STATFIELD", "ITM-XFMR", 65, 3300000,
     "Cheaper, longer lead time; used successfully on one prior project."),
    ("SUP-MERIDIAN",  "ITM-XFMR", 58, 3600000,
     "Fastest of the three, priced at a premium, bundled service contract available."),

    # HT Cable 33kV XLPE
    ("SUP-VIDYUT",   "ITM-HTC", 21, 1080,
     "Same vendor as transformers, consistent quality on prior HT cable orders."),
    ("SUP-RAJCABLE", "ITM-HTC", 24, 1020,
     "Cheaper, standard lead time for this gauge."),
    ("SUP-GANGA",    "ITM-HTC", 26, 990,
     "Cheapest quote, no adverse notes on file yet — first order pending."),
]

# item_id, warehouse_id, qty_on_hand, qty_reserved, qty_in_transit
STOCK = [
    ("ITM-MOD540", "WH-CENTRAL", 165000, 0, 40000),
    ("ITM-INVSTR", "WH-CENTRAL", 280,    0, 100),
    ("ITM-INVCTL", "WH-CENTRAL", 10,     0, 8),  # SCENARIO 1: 18 available < 24 combined demand (15+9)
    ("ITM-MC4",    "WH-CENTRAL", 9000,   0, 0),
    ("ITM-DCC4",   "WH-CENTRAL", 18000,  0, 5000),
    ("ITM-DCC6",   "WH-CENTRAL", 42000,  0, 10000),
    ("ITM-ACC300", "WH-CENTRAL", 9500,   0, 2000),
    ("ITM-MMS",    "WH-CENTRAL", 950,    0, 200),
    ("ITM-SCB12",  "WH-CENTRAL", 85,     0, 20),
    ("ITM-EARTH",  "WH-CENTRAL", 26000,  0, 4000),
    ("ITM-LA",     "WH-CENTRAL", 45,     0, 0),
    ("ITM-JB",     "WH-CENTRAL", 200,    0, 0),
    ("ITM-ACDB",   "WH-CENTRAL", 20,     0, 5),
    ("ITM-XFMR",   "WH-CENTRAL", 3,      0, 1),
    ("ITM-HTC",    "WH-CENTRAL", 4200,   0, 1000),
]

# project_id, item_id, qty_reserved, priority_inputs_json
RESERVATIONS = [
    # SCENARIO 1: identical priority_inputs_json ties the raw score for any weighting.
    # The seam is in contract_notes_text (see PROJECTS above), not in these numbers.
    ("PRJ-BHADLA2", "ITM-INVCTL", 15,
     '{"revenue_at_risk": 42000000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),
    ("PRJ-PAVAGADA", "ITM-INVCTL", 9,
     '{"revenue_at_risk": 42000000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),

    ("PRJ-BHADLA2", "ITM-XFMR", 2,
     '{"revenue_at_risk": 55500000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.35}'),
    ("PRJ-PAVAGADA", "ITM-XFMR", 1,
     '{"revenue_at_risk": 33000000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),

    ("PRJ-BHADLA2", "ITM-MMS", 500,
     '{"revenue_at_risk": 55500000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),
    ("PRJ-PAVAGADA", "ITM-MMS", 300,
     '{"revenue_at_risk": 33000000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),
    ("PRJ-GUJHYBRID", "ITM-MMS", 400,
     '{"revenue_at_risk": 42600000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.25}'),

    ("PRJ-BHADLA2", "ITM-SCB12", 40,
     '{"revenue_at_risk": 55500000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),
    ("PRJ-PAVAGADA", "ITM-SCB12", 24,
     '{"revenue_at_risk": 33000000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.3}'),
    ("PRJ-GUJHYBRID", "ITM-SCB12", 32,
     '{"revenue_at_risk": 42600000, "penalty_exposure_pct_per_day": 0.3, "delay_probability": 0.25}'),
]

TABLES_IN_DELETE_ORDER = [
    "agent_recommendations",
    "reservations",
    "bom",
    "suppliers",
    "stock",
    "projects",
    "items",
]


def seed(conn) -> None:
    for table in TABLES_IN_DELETE_ORDER:
        conn.execute(f"DELETE FROM {table}")

    conn.executemany(
        "INSERT INTO items (item_id, name, category, unit) VALUES (?, ?, ?, ?)",
        ITEMS,
    )
    conn.executemany(
        "INSERT INTO projects (project_id, name, cod_deadline, contract_value, contract_notes_text) "
        "VALUES (?, ?, ?, ?, ?)",
        PROJECTS,
    )
    conn.executemany(
        "INSERT INTO bom (project_id, item_id, qty_required, milestone_date) VALUES (?, ?, ?, ?)",
        BOM,
    )
    conn.executemany(
        "INSERT INTO suppliers (supplier_id, item_id, lead_time_days, unit_price, notes_text) "
        "VALUES (?, ?, ?, ?, ?)",
        SUPPLIERS,
    )
    conn.executemany(
        "INSERT INTO stock (item_id, warehouse_id, qty_on_hand, qty_reserved, qty_in_transit) "
        "VALUES (?, ?, ?, ?, ?)",
        STOCK,
    )
    conn.executemany(
        "INSERT INTO reservations (project_id, item_id, qty_reserved, priority_inputs_json) VALUES (?, ?, ?, ?)",
        RESERVATIONS,
    )

    conn.commit()


def main() -> None:
    conn = get_connection()
    seed(conn)
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in reversed(TABLES_IN_DELETE_ORDER)
    }
    conn.close()
    for table, count in counts.items():
        print(f"{table}: {count} rows")


if __name__ == "__main__":
    main()
