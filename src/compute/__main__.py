"""CLI sanity check: prints reorder points/EOQ and contested-item priority
scores computed from the current seeded DB. Not a tool the agent calls -- a
manual gut-check before Week 3 wires the compute layer into the agent loop.

Run with `python -m src.compute`.
"""

import datetime
import json

from src.compute.priority_score import calculate_priority_score, rank_by_priority
from src.compute.reorder import calculate_eoq, calculate_reorder_point, reorder_recommendation
from src.db.connection import get_connection

ORDER_COST = 5000  # INR, flat per-PO estimate -- Week 3 can refine per item if needed
HOLDING_COST_RATE = 0.2  # 20% of unit price per year, standard EPC carrying-cost estimate


def days_until(today: datetime.date, iso_date: str) -> int:
    target = datetime.date.fromisoformat(iso_date)
    return max((target - today).days, 0)


def print_reorder_table(conn, today: datetime.date) -> None:
    print("=== Reorder point / EOQ per item ===")
    items = conn.execute("SELECT item_id, name FROM items ORDER BY item_id").fetchall()

    for item in items:
        item_id = item["item_id"]

        stock = conn.execute(
            "SELECT SUM(qty_on_hand) AS oh, SUM(qty_in_transit) AS it FROM stock WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        available = (stock["oh"] or 0) + (stock["it"] or 0)

        bom_rows = conn.execute(
            "SELECT qty_required, milestone_date FROM bom WHERE item_id = ?", (item_id,)
        ).fetchall()
        suppliers = conn.execute(
            "SELECT lead_time_days, unit_price FROM suppliers WHERE item_id = ?", (item_id,)
        ).fetchall()
        if not bom_rows or not suppliers:
            continue

        total_demand = sum(r["qty_required"] for r in bom_rows)
        nearest_milestone = min(r["milestone_date"] for r in bom_rows)
        days_out = days_until(today, nearest_milestone)
        daily_demand = total_demand / max(days_out, 1)

        lead_time_days = min(s["lead_time_days"] for s in suppliers)
        avg_price = sum(s["unit_price"] for s in suppliers) / len(suppliers)

        rop = calculate_reorder_point(daily_demand=daily_demand, lead_time_days=lead_time_days)
        eoq = calculate_eoq(
            annual_demand=daily_demand * 365,
            order_cost=ORDER_COST,
            holding_cost_per_unit=avg_price * HOLDING_COST_RATE,
        )
        rec = reorder_recommendation(available_stock=available, reorder_point=rop, eoq_qty=eoq)
        flag = "REORDER NOW" if rec["should_reorder"] else "ok"

        print(
            f"{item_id:12} {item['name']:30} avail={available:>9.0f}  "
            f"rop={rop:>9.1f}  eoq={eoq:>9.1f}  [{flag}]"
        )


def print_priority_table(conn, today: datetime.date) -> None:
    print("\n=== Priority scores for contested items ===")
    contested = conn.execute(
        "SELECT item_id FROM reservations GROUP BY item_id HAVING COUNT(DISTINCT project_id) > 1"
    ).fetchall()

    for row in contested:
        item_id = row["item_id"]
        print(f"\n{item_id}:")

        reservations = conn.execute(
            "SELECT project_id, qty_reserved, priority_inputs_json FROM reservations WHERE item_id = ?",
            (item_id,),
        ).fetchall()

        scores = {}
        for r in reservations:
            inputs = json.loads(r["priority_inputs_json"])
            bom_row = conn.execute(
                "SELECT milestone_date FROM bom WHERE item_id = ? AND project_id = ?",
                (item_id, r["project_id"]),
            ).fetchone()
            days_out = days_until(today, bom_row["milestone_date"]) if bom_row else 0

            score = calculate_priority_score(days_to_deadline=days_out, **inputs)
            scores[r["project_id"]] = score
            print(f"  {r['project_id']:16} qty={r['qty_reserved']:>6}  score={score:>8.2f}")

        ranking = rank_by_priority(scores)
        print("  ranking: " + " > ".join(project_id for project_id, _ in ranking))


def main() -> None:
    conn = get_connection()
    if conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0:
        print("Database is empty. Run `python -m src.db.seed_data` first.")
        conn.close()
        return

    today = datetime.date.today()
    print_reorder_table(conn, today)
    print_priority_table(conn, today)
    conn.close()


if __name__ == "__main__":
    main()
