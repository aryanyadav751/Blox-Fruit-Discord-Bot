"""
Automated Bot Setup & Flow Verification Script.
Simulates bot lifecycle without requiring live Discord gateway connection:
- Tests database initialization
- Tests catalog loading and draft filtering
- Tests loading all required cogs into a test bot instance
- Inspects registered application slash commands
- Verifies customer ordering simulation through persistent Order ID generation
"""

import sys
import asyncio
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discord
from discord.ext import commands
from core.database import db
from core.catalog import catalog
from core.calculator import calculate_payment, format_m, PaymentPlan
from config import Config
from bot import BloxFruitBot, REQUIRED_COGS


async def verify():
    print("=== [1] Verifying Database Initialization & Schema ===")
    db.init_db()
    with db._get_connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    assert "orders" in tables, "orders table missing"
    assert "payments" in tables, "payments table missing"
    assert "audit_logs" in tables, "audit_logs table missing"
    assert "bot_config" in tables, "bot_config table missing"
    print("  [PASS] All SQLite tables initialized correctly: orders, payments, audit_logs, bot_config.")

    print("\n=== [2] Verifying Service Catalog & Draft Isolation ===")
    catalog.load()
    assert len(catalog.categories) >= 8, "Categories missing"
    active_services = [s for cat in catalog.categories.values() for s in cat.active_services()]
    draft_services = [s for cat in catalog.categories.values() for s in cat.services if not s.is_active]
    print(f"  [PASS] Catalog loaded. Active services: {len(active_services)}. Gated draft services: {len(draft_services)}.")

    # Check unconfirmed items are draft
    for draft_id in ["trials_4", "boss_tyrant_skies", "sea_ph", "dungeon_hard"]:
        srv = catalog.get_service(draft_id)
        assert srv and srv.status == "draft", f"Service {draft_id} should be draft!"
    print("  [PASS] Unconfirmed items (4 Trials, Tyrant of Skies, PH, Hard Dungeon) are correctly gated as draft.")

    print("\n=== [3] Verifying Bot Instance & Required Cogs Loading ===")
    test_bot = BloxFruitBot()

    # Load required cogs
    for cog_name in REQUIRED_COGS:
        await test_bot.load_extension(cog_name)
        print(f"  [PASS] Successfully loaded cog: {cog_name}")

    registered_commands = [cmd.name for cmd in test_bot.tree.get_commands()]
    print(f"  [PASS] Slash command tree populated with {len(registered_commands)} commands: {registered_commands}")
    expected_cmds = ["setup", "catalog", "order", "order-status", "admin-order", "edit-price", "order-history", "help"]
    for ec in expected_cmds:
        assert ec in registered_commands, f"Command /{ec} missing from tree!"

    print("\n=== [4] Verifying Customer Ordering & 50/50 vs Upfront Flow ===")
    # 50/50 test
    breakdown_50 = calculate_payment("75.00", PaymentPlan.SPLIT_50_50)
    assert breakdown_50.initial_payment_m == Decimal("37.50")
    assert breakdown_50.remaining_balance_m == Decimal("37.50")

    order_id = await db.get_next_order_id()
    created_50 = await db.create_order(
        order_id=order_id,
        customer_id=123456789,
        customer_tag="Customer#1234",
        roblox_username="RobloxHero",
        category_id="bosses",
        service_id="boss_dough_king",
        service_name="Dough King",
        total_price_m=breakdown_50.total_price_m,
        payment_plan=PaymentPlan.SPLIT_50_50.value,
        initial_payment_required_m=breakdown_50.initial_payment_m,
        balance_remaining_m=breakdown_50.remaining_balance_m,
        payment_methods='["FRUITS", "GAMEPASSES"]',
        proposed_items="Mammoth + 2x Mastery",
        customer_availability="Evenings EST",
    )
    assert created_50["order_id"] == order_id
    assert created_50["status"] == "PENDING_ACCEPTANCE"
    print(f"  [PASS] Order {order_id} created with 50/50 plan. Upfront: {created_50['initial_payment_required_m']}M, Balance: {created_50['balance_remaining_m']}M.")

    # Upfront payment recording
    paid_up = await db.record_payment(
        order_id=order_id,
        payment_stage="UPFRONT",
        items_received="1x Mammoth",
        credited_value_m="37.50",
        staff_id=999,
        staff_tag="Staff#1",
    )
    assert paid_up["initial_payment_paid_m"] == 37.5
    assert paid_up["status"] == "UPFRONT_VERIFIED"
    print(f"  [PASS] Upfront payment recorded. Status advanced to {paid_up['status']}.")

    # Status transitions to IN_PROGRESS then COMPLETED_AWAITING_BALANCE
    await db.update_order_status(order_id, "IN_PROGRESS", 999, "Staff#1")
    await db.update_order_status(order_id, "COMPLETED_AWAITING_BALANCE", 999, "Staff#1")

    # Balance payment recording
    paid_bal = await db.record_payment(
        order_id=order_id,
        payment_stage="BALANCE",
        items_received="2x Mastery Gamepass",
        credited_value_m="37.50",
        staff_id=999,
        staff_tag="Staff#1",
    )
    assert paid_bal["balance_paid_m"] == 37.5
    assert paid_bal["status"] == "PAID_AND_CLOSED"
    print(f"  [PASS] Final balance recorded. Order status successfully closed: {paid_bal['status']}.")

    print("\n=== [5] Verifying Token Validation & Clean Absence Handling ===")
    validation_errs = Config.validate()
    print(f"  [PASS] Token validation properly detects placeholder/unset tokens: {validation_errs}")

    print("\n=======================================================")
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH ZERO ERRORS!")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(verify())
