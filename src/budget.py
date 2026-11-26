"""Persistent conservative reservations for estimated API costs.

This is not a provider-enforced spending cap. Configure account-level limits too.
"""
from decimal import Decimal, InvalidOperation
import sqlite3
from .providers import ProviderError

def _microdollars(value) -> int:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0:
            raise ValueError("Invalid price")
        scaled = amount * 1_000_000
        if scaled != scaled.to_integral_value():
            raise ValueError("Use at most six decimal places")
        return int(scaled)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid price") from exc

class PersistentAllowance:
    def __init__(self, conn: sqlite3.Connection, run_id: int, *, approved: bool,
                 max_serp: int, max_llm: int, budget_usd, serp_reservation_usd, llm_reservation_usd):
        if type(max_serp) is not int or type(max_llm) is not int or min(max_serp, max_llm) < 0:
            raise ValueError("Invalid request limits")
        self.conn, self.run_id, self.approved = conn, run_id, approved
        self.limits = {"serp": max_serp, "llm": max_llm}
        self.budget = _microdollars(budget_usd)
        self.prices = {"serp": _microdollars(serp_reservation_usd), "llm": _microdollars(llm_reservation_usd)}
        if self.budget <= 0 or any(v <= 0 for v in self.prices.values()):
            raise ValueError("Budget and reservations must be positive")
        conn.execute("""CREATE TABLE IF NOT EXISTS request_reservations (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
            service TEXT NOT NULL, estimated_microusd INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
    def take(self, service: str) -> None:
        if not self.approved: raise ProviderError("Paid requests require explicit approval")
        if service not in self.limits: raise ValueError("Unknown service")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self.conn.execute("SELECT service, COUNT(*) AS n, SUM(estimated_microusd) AS cost FROM request_reservations WHERE run_id=? GROUP BY service", (self.run_id,)).fetchall()
            counts = {row["service"]: row["n"] for row in rows}
            spent = sum(row["cost"] for row in rows)
            if counts.get(service, 0) >= self.limits[service]: raise ProviderError("Request limit reached")
            if spent + self.prices[service] > self.budget: raise ProviderError("Estimated budget exhausted")
            self.conn.execute("INSERT INTO request_reservations(run_id, service, estimated_microusd) VALUES (?, ?, ?)",
                              (self.run_id, service, self.prices[service]))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
