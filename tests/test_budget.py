import unittest
from src.budget import PersistentAllowance
from src.database import connect
from src.providers import ProviderError

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.addCleanup(self.db.close)
        self.run = self.db.execute("INSERT INTO runs(started_at,mode,status) VALUES ('now','live','running')").lastrowid
        self.db.commit()
    def allowance(self, approved=True):
        return PersistentAllowance(self.db, self.run, approved=approved, max_serp=2, max_llm=4,
             budget_usd="0.03", serp_reservation_usd="0.01", llm_reservation_usd="0.02")
    def test_persists_budget_across_restart(self):
        self.allowance().take("serp")
        self.allowance().take("llm")
        with self.assertRaises(ProviderError): self.allowance().take("serp")
        self.assertEqual(self.db.execute("SELECT count(*) FROM request_reservations").fetchone()[0], 2)
    def test_no_approval_no_reservation(self):
        with self.assertRaises(ProviderError): self.allowance(False).take("serp")
        self.assertEqual(self.db.execute("SELECT count(*) FROM request_reservations").fetchone()[0], 0)
    def test_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            PersistentAllowance(self.db, self.run, approved=True, max_serp=1, max_llm=1,
                budget_usd="nan", serp_reservation_usd="0.01", llm_reservation_usd="0.01")

if __name__ == "__main__": unittest.main()
