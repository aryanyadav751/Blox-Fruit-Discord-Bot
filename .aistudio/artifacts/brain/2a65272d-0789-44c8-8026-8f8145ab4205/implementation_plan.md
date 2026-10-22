# Blox Fruit Services — Complete Discord Booking Bot (Revised Plan)

A dedicated Discord-only service booking bot for Blox Fruits built with Python 3.11, `discord.py`, and SQLite persistence. Designed for mobile and desktop operation, with strictly in-game trade values in Millions (M), zero real-money transactions, zero credential collection, and no paid cloud services.

---

## User Review & Critical Decisions

> [!IMPORTANT]
> The following architectural revisions and confirmed rules have been integrated:

- **Confirmed Revision 1 (Two-Part Payment Preference Flow)**:
  - **Part 3A (Payment Plan)**: Customers select between:
    1. **50/50 Payment**: 50% upfront deposit, 50% remaining balance upon service completion.
    2. **One-Time Full Payment**: 100% upfront payment, 0M remaining balance.
  - **Part 3B (Payment Method)**: Customers select one or more in-game payment methods:
    - *Fruits*
    - *Gamepasses*
    - *Combination of Fruits and Gamepasses*
- **Confirmed Revision 2 (Exact Split & Rounding Assurance)**:
  - For **One-Time Full Payment**: `initial_deposit_m = total_price_m`, `balance_remaining_m = 0.0`.
  - For **50/50 Payment**: Initial deposit is calculated as `round(total_price_m / 2.0, 2)`. To guarantee absolute mathematical consistency with odd or non-divisible numbers:
    $$\text{balance\_remaining\_m} = \text{total\_price\_m} - \text{initial\_deposit\_m}$$
    $$\text{initial\_deposit\_m} + \text{balance\_remaining\_m} \equiv \text{total\_price\_m}$$
- **Confirmed Revision 3 (Adaptive Staff Controls by Plan)**:
  - For **50/50 orders**: Staff tracks two sequential payment events: Initial Deposit received $\rightarrow$ Service completed $\rightarrow$ Remaining Balance received $\rightarrow$ Order closed.
  - For **One-Time Full orders**: Staff tracks a single upfront payment event: Full Payment received $\rightarrow$ Service completed $\rightarrow$ Order closed directly without an unnecessary remaining balance phase.
- **Confirmed Revision 4 (Zero-Cost & Persistence Policy)**: Local SQLite storage (`data/blox_fruits.db`). No Cloud SQL, no paid APIs, and no real-money payment processors.
- **Confirmed Revision 5 (Draft Catalog Isolation)**: All unconfirmed rates and ambiguous abbreviations remain hidden from customers until verified by staff.

---

## 1. Overview & Core Concept

- **What It Does**: Automates Blox Fruits in-game service bookings. Customers browse published services, select a 50/50 split or One-Time upfront plan, specify their payment methods (fruits/gamepasses), and submit their Roblox username and play times.
- **Staff Order Thread**: Generates a dedicated private thread (`#order-BFS-XXXX`) in the staff channel. Staff reviews the proposed items, verifies trades in Roblox, logs item names and credited M values, and transitions order states.
- **Customer DMs**: Real-time notifications dispatched to the customer at each state change. If DMs fail, the order is safely retained and staff is notified in the thread.

---

## 2. Updated User Experience & Discord Interaction Flows

### Customer Ordering Sequence (`#order-here` or `/order`)

```
[ Persistent Embed: Blox Fruit Services ]
[ 🛒 Order Now Button ]
       │
       ▼
[ Step 1: Category Select (Trials, Bosses, Swords, Progression, Raids, Sea Events) ]
       │
       ▼
[ Step 2: Service Select (Displays Price in M, Prerequisites, Exclusions) ]
       │
       ▼
[ Step 3: Discord Interaction / Form View ]
  ├── Part 3A — Payment Plan Selection:
  │     (•) 50/50 Payment (50% upfront, 50% on completion)
  │     ( ) One-Time Full Payment (100% upfront, 0M balance)
  │
  ├── Part 3B — Payment Method Selection (Multi-select or buttons):
  │     [☑ Fruits]  [☑ Gamepasses]  [☑ Combination]
  │
  └── Order Details Modal:
        ├── Roblox Username
        ├── Timezone & Available Play Hours
        └── Proposed Items & Estimated Values (e.g. "Dragon + Dough = ~110M")
       │
       ▼
[ Step 4: Ephemeral Order Confirmation Card ]
  ├── Service & Category
  ├── Total Agreed Value (e.g. 150.0M)
  ├── Selected Plan: 50/50 Payment or One-Time Full Payment
  ├── Upfront Due (e.g. 75.0M) & Remaining Balance (e.g. 75.0M or 0.0M)
  ├── Preferred Methods: Fruits & Gamepasses
  ├── Proposed Item Breakdown
  └── Buttons: [ ✅ Confirm Order ]  [ ❌ Cancel ]
```

### Staff Management Sequence (`#staff-orders` + Private Thread)

```
[ Order Confirmed by Customer ]
       │
       ▼
[ Bot generates Order ID (e.g. BFS-1042) ]
[ Bot posts Master Embed in #staff-orders & creates Private Thread: 🧵 order-bfs-1042 ]
       │
       ▼
[ Inside Staff Thread: Detailed Embed ]
  ├── Customer: @Username (ID) | Roblox: GamerPro_123
  ├── Service: Dough King (Bosses) — 75.0M
  ├── Payment Plan: 50/50 Split (Upfront: 37.5M | Remaining: 37.5M)
  ├── Payment Method: Combination (Fruits + Gamepasses)
  ├── Customer Proposed Offer: "Mammoth (15M) + 2x Mastery (25M) = 40M"
  ├── Availability: UTC+5:30 (Evenings 7-10 PM)
  └── Payment Verification Status: ⏳ AWAITING VERIFICATION
       │
       ▼
[ Adaptive Staff Action Buttons ]
  ├── For 50/50 Plan:
  │     [ ✅ Accept Order ]
  │     [ 💰 Record Deposit (Upfront) ] -> Logs items & credited M -> Status: DEPOSIT_VERIFIED
  │     [ ⚔️ Start Service ]            -> Status: IN_PROGRESS
  │     [ 🎉 Mark Completed ]           -> Status: COMPLETED_PENDING_BALANCE
  │     [ 💳 Record Balance ]           -> Logs balance items -> Status: PAID_AND_CLOSED
  │
  ├── For One-Time Full Plan:
  │     [ ✅ Accept Order ]
  │     [ 💰 Record Full Payment ]     -> Logs items & credited M -> Status: FULLY_PAID
  │     [ ⚔️ Start Service ]            -> Status: IN_PROGRESS
  │     [ 🎉 Mark Completed & Close ]   -> Status: PAID_AND_CLOSED (directly)
  │
  └── Common Utilities:
        [ ❓ Request Info ]              -> Modal: Sends custom DM to customer
        [ ❌ Cancel / Reject ]           -> Modal: Mandatory cancellation reason
```

---

## 3. Database Schema Revisions (`schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,                 -- e.g. 'BFS-1042'
    customer_id INTEGER NOT NULL,              -- Discord User ID
    customer_tag TEXT NOT NULL,                -- e.g. 'Customer#1234'
    roblox_username TEXT NOT NULL,             -- In-game username
    category_id TEXT NOT NULL,
    service_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    total_price_m REAL NOT NULL,               -- Agreed trade value in M
    payment_plan TEXT NOT NULL,                -- 'SPLIT_50_50' or 'FULL_UPFRONT'
    initial_payment_required_m REAL NOT NULL,  -- Upfront deposit or full amount
    balance_remaining_m REAL NOT NULL,         -- Remaining balance (0.0 for full upfront)
    initial_payment_paid_m REAL DEFAULT 0.0,
    balance_paid_m REAL DEFAULT 0.0,
    payment_methods TEXT NOT NULL,             -- JSON array or CSV: '["fruits", "gamepass"]'
    proposed_items TEXT NOT NULL,              -- Declared items & estimated values
    customer_availability TEXT NOT NULL,       -- Timezone & play times
    status TEXT NOT NULL,                      -- PENDING_ACCEPTANCE, AWAITING_UPFRONT_PAYMENT, UPFRONT_PAID, IN_PROGRESS, COMPLETED_AWAITING_BALANCE, PAID_AND_CLOSED, CANCELLED, REJECTED
    staff_thread_id INTEGER,                   -- Dedicated Discord Thread ID
    staff_message_id INTEGER,                  -- Master embed message ID
    assigned_staff_id INTEGER,
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    payment_stage TEXT NOT NULL,               -- 'UPFRONT' or 'BALANCE' or 'ADJUSTMENT'
    items_received TEXT NOT NULL,              -- Exact fruits/gamepasses traded
    credited_value_m REAL NOT NULL,            -- Verified in-game trade value
    verified_by_staff_id INTEGER NOT NULL,
    verified_by_staff_tag TEXT NOT NULL,
    notes TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    action TEXT NOT NULL,                      -- 'ORDER_SUBMITTED', 'ACCEPTED', 'UPFRONT_PAYMENT_LOGGED', etc.
    actor_id INTEGER NOT NULL,
    actor_tag TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

CREATE TABLE IF NOT EXISTS bot_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

## 4. Draft Catalog & Review Checklist

Uncertain entries remain flagged with `"status": "draft"` and will **not** appear in public dropdowns:
- **4 Trials (160M)**: Handwritten rate to confirm.
- **Other Materials (150K–1.5M)**: Marked as quote-only draft.
- **Tyrant of the Skies (75M)**: Handwritten rate to confirm.
- **Cyborg V1 (150M)**: Flagged with "F.O.D. included" verification.
- **V2 + V3 Bundle (35M–50M)**: Range requires exact price or staff quote.
- **Level 100**: Price unclear.
- **PH & PH with magnets (50M/30M)**: Abbreviation to confirm with owner.
- **Dough Full Awakening (30M)**: Prerequisites to verify.
- **Low Raids (2.5M)**: Scope of raids to clarify.
- **Raids to Core Break (70M)**: Clarify objective.
- **Dungeon Hard (50M)**: Handwritten price to confirm.
- **10M Beli (45M)**: Conversion rate to confirm.

---

## 5. Automated Testing Strategy (Pytest Suite)

A dedicated, comprehensive test suite (`tests/`) will cover:
1. **Payment Calculation & Split Invariance**:
   - 50/50 split on even numbers (e.g. 150M $\rightarrow$ 75.0M initial, 75.0M balance).
   - 50/50 split on odd numbers (e.g. 75M $\rightarrow$ 37.5M initial, 37.5M balance).
   - 50/50 split on fractional numbers (e.g. 2.5M $\rightarrow$ 1.25M initial, 1.25M balance).
   - Strict equation check: `initial + remaining == total`.
   - One-Time Full payment: `initial == total`, `remaining == 0.0`.
2. **Payment Method Selections**:
   - Single method: Fruits only or Gamepass only.
   - Combined methods: Fruits + Gamepasses.
3. **Database Transactions & Persistence**:
   - Order creation, persistent ID generation (`BFS-1001`, `BFS-1002`).
   - Payment record insertion and credit tracking.
   - Audit trail entries on state transitions.
4. **Staff Permission Checks**:
   - Verify that non-staff users cannot execute staff actions or payment logging.
5. **Idempotency & Race Conditions**:
   - Prevent duplicate order creation on rapid button clicks.
   - Prevent double payment logging.
6. **Customer Notification Resilience**:
   - Fallback handling when customer DMs are blocked.

---

## 6. Affected Project Files

The implementation will be organized into a clean, modular structure:

1. **`requirements.txt`**: `discord.py>=2.3.0`, `python-dotenv>=1.0.0`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`.
2. **`.env.example`**: Clean template with `DISCORD_BOT_TOKEN`, `GUILD_ID`, `STAFF_ROLE_ID`, `STAFF_CHANNEL_ID`, `ORDER_CHANNEL_ID`.
3. **`.gitignore`**: Excludes `data/*.db`, `.env`, `__pycache__`, `.pytest_cache`.
4. **`config.py`**: Environment variable loader, path constants, and runtime defaults.
5. **`core/database.py`**: SQLite async wrapper, schema initialization, and transactional queries.
6. **`core/catalog.py`**: Catalog loader, draft filtering, and price retrieval.
7. **`core/calculator.py`**: Payment plan split engine, rounding guarantees, and currency formatting.
8. **`cogs/ordering.py`**: Customer UI, category & service selects, Part 3A & 3B payment preference menus, order modal, and summary card.
9. **`cogs/staff_controls.py`**: Staff order embed, private thread creation, payment recording modals (upfront vs balance), audit logging, and customer DM dispatcher.
10. **`cogs/admin_commands.py`**: Slash commands (`/setup`, `/catalog`, `/order-status`, `/admin-order`, `/edit-price`, `/order-history`, `/help`).
11. **`bot.py`**: Discord bot initialization, persistent view registration across restarts, and slash command synchronization.
12. **`tests/test_calculator.py`**, **`tests/test_database.py`**, **`tests/test_ordering.py`**: Automated test suite.
13. **`data/catalog.json`**: Pre-seeded catalog with verified prices and draft-tagged unconfirmed items.
14. **`README.md`**: Step-by-step phone-friendly guide to creating the Discord Bot on Discord Developer Portal, inviting it, configuring `.env`, and deploying on Railway/Render/VPS with zero cost.
