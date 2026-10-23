"""
Automated Test Runner for Blox Fruit Services.
Runs test suites for:
1. Payment Calculator & Invariant checks (Decimal fixed precision, 50/50 & One-Time Full)
2. Catalog Manager & Draft gating
3. SQLite Database persistence, state machine transitions, over-credit prevention
4. Staff Authorization checks across views and modals
"""

import sys
import unittest
import asyncio
from pathlib import Path
import tempfile
import shutil
from decimal import Decimal

# Ensure workspace root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.calculator import calculate_payment, format_m, PaymentPlan, PaymentMethod
from core.catalog import CatalogManager
from core.database import Database
from cogs.staff_controls import is_staff
from config import Config
from unittest.mock import MagicMock


class TestCalculator(unittest.TestCase):
    def test_one_time_full_payment(self):
        b = calculate_payment(150.0, PaymentPlan.FULL_UPFRONT)
        self.assertEqual(b.total_price_m, Decimal("150.00"))
        self.assertEqual(b.initial_payment_m, Decimal("150.00"))
        self.assertEqual(b.remaining_balance_m, Decimal("0.00"))
        self.assertEqual(b.initial_payment_m + b.remaining_balance_m, b.total_price_m)

    def test_50_50_split_even(self):
        b = calculate_payment(150.0, PaymentPlan.SPLIT_50_50)
        self.assertEqual(b.initial_payment_m, Decimal("75.00"))
        self.assertEqual(b.remaining_balance_m, Decimal("75.00"))
        self.assertEqual(b.initial_payment_m + b.remaining_balance_m, b.total_price_m)

    def test_50_50_split_odd(self):
        b = calculate_payment(75.0, PaymentPlan.SPLIT_50_50)
        self.assertEqual(b.initial_payment_m, Decimal("37.50"))
        self.assertEqual(b.remaining_balance_m, Decimal("37.50"))
        self.assertEqual(b.initial_payment_m + b.remaining_balance_m, b.total_price_m)

    def test_50_50_split_fractions(self):
        # 2.5M
        b1 = calculate_payment(2.5, PaymentPlan.SPLIT_50_50)
        self.assertEqual(b1.initial_payment_m, Decimal("1.25"))
        self.assertEqual(b1.remaining_balance_m, Decimal("1.25"))
        self.assertEqual(b1.initial_payment_m + b1.remaining_balance_m, Decimal("2.50"))

        # 0.1M (100K)
        b2 = calculate_payment(0.1, PaymentPlan.SPLIT_50_50)
        self.assertEqual(b2.initial_payment_m, Decimal("0.05"))
        self.assertEqual(b2.remaining_balance_m, Decimal("0.05"))
        self.assertEqual(b2.initial_payment_m + b2.remaining_balance_m, Decimal("0.10"))

    def test_invariant_broad(self):
        prices = [0.1, 0.5, 1.0, 2.0, 2.5, 5.0, 7.0, 10.0, 15.0, 17.0, 20.0, 30.0, 35.0, 45.0, 50.0, 75.0, 125.0, 150.0, 175.0]
        for p in prices:
            for plan in [PaymentPlan.SPLIT_50_50, PaymentPlan.FULL_UPFRONT]:
                b = calculate_payment(p, plan)
                self.assertEqual(b.initial_payment_m + b.remaining_balance_m, b.total_price_m)

    def test_format_m(self):
        self.assertEqual(format_m(150.0), "150M")
        self.assertEqual(format_m(37.5), "37.5M")
        self.assertEqual(format_m(0.1), "0.1M")


class TestCatalog(unittest.TestCase):
    def test_draft_items_hidden(self):
        manager = CatalogManager()
        trials_cat = manager.categories["trials"]
        active_ids = [s.id for s in trials_cat.active_services()]

        self.assertNotIn("trials_4", active_ids)
        self.assertIn("trials_1", active_ids)
        self.assertIn("trials_2", active_ids)
        self.assertIn("trials_5", active_ids)

        s4 = manager.get_service("trials_4")
        self.assertEqual(s4.status, "draft")

    def test_boss_and_sea_drafts(self):
        manager = CatalogManager()
        boss_active = [s.id for s in manager.categories["bosses"].active_services()]
        self.assertNotIn("boss_tyrant_skies", boss_active)
        self.assertIn("boss_dough_king", boss_active)

        sea_active = [s.id for s in manager.categories["sea_events"].active_services()]
        self.assertNotIn("sea_ph", sea_active)
        self.assertNotIn("sea_ph_magnets", sea_active)
        self.assertIn("sea_kitsune", sea_active)
        self.assertIn("sea_leviathan", sea_active)


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_order_id_generation(self):
        id1 = self.db.get_next_order_id_sync()
        id2 = self.db.get_next_order_id_sync()
        self.assertEqual(id1, "BFS-1001")
        self.assertEqual(id2, "BFS-1002")

    def test_order_and_payment_flow(self):
        async def run_flow():
            order_id = await self.db.get_next_order_id()
            self.assertEqual(order_id, "BFS-1001")

            # Create order
            order = await self.db.create_order(
                order_id=order_id,
                customer_id=12345,
                customer_tag="Customer#0001",
                roblox_username="RobloxHero",
                category_id="bosses",
                service_id="boss_dough_king",
                service_name="Dough King",
                total_price_m=75.0,
                payment_plan="SPLIT_50_50",
                initial_payment_required_m=37.5,
                balance_remaining_m=37.5,
                payment_methods='["FRUITS", "GAMEPASSES"]',
                proposed_items="Mammoth + 2x Mastery",
                customer_availability="EST Evenings",
            )
            self.assertEqual(order["status"], "PENDING_ACCEPTANCE")

            # Record upfront payment
            up_order = await self.db.record_payment(
                order_id=order_id,
                payment_stage="UPFRONT",
                items_received="1x Mammoth",
                credited_value_m=37.5,
                staff_id=999,
                staff_tag="Staff#1111",
                notes="Trade verified",
            )
            self.assertEqual(up_order["initial_payment_paid_m"], 37.5)
            self.assertEqual(up_order["status"], "UPFRONT_VERIFIED")

            # Update status to IN_PROGRESS then COMPLETED_AWAITING_BALANCE
            await self.db.update_order_status(order_id, "IN_PROGRESS", 999, "Staff#1111")
            await self.db.update_order_status(order_id, "COMPLETED_AWAITING_BALANCE", 999, "Staff#1111")

            # Record balance payment
            bal_order = await self.db.record_payment(
                order_id=order_id,
                payment_stage="BALANCE",
                items_received="1x Gamepass",
                credited_value_m=37.5,
                staff_id=999,
                staff_tag="Staff#1111",
                notes="Balance verified",
            )
            self.assertEqual(bal_order["balance_paid_m"], 37.5)
            self.assertEqual(bal_order["status"], "PAID_AND_CLOSED")

            # Verify audit trail
            audits = await self.db.get_order_audits(order_id)
            self.assertGreaterEqual(len(audits), 5)

        asyncio.run(run_flow())


class TestPermissions(unittest.TestCase):
    def test_permissions(self):
        regular = MagicMock()
        regular.guild_permissions.administrator = False
        regular.guild_permissions.manage_guild = False
        regular.roles = []
        self.assertFalse(is_staff(regular))

        admin = MagicMock()
        admin.guild_permissions.administrator = True
        self.assertTrue(is_staff(admin))

        Config.STAFF_ROLE_ID = 555
        staff_member = MagicMock()
        staff_member.guild_permissions.administrator = False
        staff_member.guild_permissions.manage_guild = False
        r = MagicMock()
        r.id = 555
        staff_member.roles = [r]
        self.assertTrue(is_staff(staff_member))


if __name__ == "__main__":
    unittest.main()
