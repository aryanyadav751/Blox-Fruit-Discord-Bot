# ⚔️ Blox Fruit Services — Discord Booking Bot

A complete, production-ready Discord service booking bot for **Blox Fruits** built with **Python 3.11+**, `discord.py`, and **SQLite** persistent storage.

---

## 📌 Critical Business & Valuation Rules

1. **In-Game Trade Value Only**: All service prices, deposits, and balances are expressed in **estimated in-game Blox Fruits trade value in Millions (M)**.
2. **Zero Real-Money Transactions**: Never introduce USD, INR, cash, bank transfers, or payment gateways.
3. **No Account Credential Collection**: Never ask customers for Roblox passwords, security cookies, or two-factor authentication codes.
4. **Staff-Verified Trades**: Submitting a fruit or gamepass offer does **NOT** automatically mark it as paid. Authorized staff must conduct the in-game trade in Roblox and click the bot's verification button to credit the agreed trade value.
5. **No Paid Cloud Infrastructure**: Uses local SQLite storage (`data/blox_fruits.db`) requiring zero paid database subscriptions.

---

## 🚀 Key Features

- **🛒 Public "Order Now" Panel**: Persistent button in your `#order-here` channel that never breaks across bot restarts.
- **⚖️ Flexible Payment Plans**:
  - **50/50 Split**: 50% deposit upfront, 50% remaining balance upon service completion.
  - **One-Time Full**: 100% upfront payment with zero remaining balance.
- **🍎 Multi-Item In-Game Offers**: Customers can pay using Fruits, Gamepasses, or Combinations (e.g. Dragon + Dough = ~110M).
- **🧵 Automated Private Staff Threads**: Every confirmed order automatically spawns a dedicated private thread in `#staff-orders` (e.g. `order-bfs-1042`) where staff can chat and manage orders.
- **🛡️ Server-Side Role Authorization**: All staff controls (`Accept`, `Record Upfront Payment`, `Start Service`, `Mark Completed`, `Record Balance`, `Cancel`) enforce strict permission checks.
- **📬 Customer Direct Message (DM) Alerts**: Automatic updates sent to customers at each phase of their order, with graceful fallbacks if customer DMs are disabled.
- **🔒 Draft Catalog Isolation**: Unconfirmed prices and ambiguous abbreviations are kept hidden from customers until verified by staff.

---

## 📁 Project Structure

```text
blox-fruit-services-bot/
├── bot.py                     # Main bot launcher and persistent view registrar
├── config.py                  # Environment variable loader and settings
├── requirements.txt           # Python dependencies
├── .env.example               # Template configuration file
├── .gitignore                 # Protects database files and bot tokens
├── data/
│   ├── catalog.json           # Editable service catalog with draft status
│   └── blox_fruits.db         # Persistent SQLite database (auto-created)
├── core/
│   ├── calculator.py          # 50/50 and upfront calculations & rounding rules
│   ├── catalog.py             # Catalog manager & draft filtering engine
│   └── database.py            # SQLite async query manager, payments & audit logs
├── cogs/
│   ├── ordering.py            # Customer ordering UI, select menus, and modal
│   ├── staff_controls.py      # Private thread controls, payment modals, and DMs
│   └── admin_commands.py      # Slash commands (/setup, /catalog, /edit-price, etc.)
├── tests/
│   ├── test_calculator.py     # Split invariance & rounding tests
│   ├── test_catalog.py        # Draft gating & price update tests
│   ├── test_database.py       # Persistence, sequential IDs & payment tests
│   └── test_staff_permissions.py # Role authorization tests
├── run_tests.py               # Standalone test runner
└── README.md                  # Complete setup and deployment guide
```

---

## 📱 Phone-Friendly Setup Guide (Step-by-Step)

You can set up and run this bot entirely from your smartphone or computer!

### Step 1: Create Your Discord Application & Bot

1. Open your mobile browser and navigate to the **[Discord Developer Portal](https://discord.com/developers/applications)**.
2. Tap **"New Application"** (top right) and name it: `Blox Fruit Services`.
3. In the left menu, tap **"Bot"**:
   - Tap **"Reset Token"** and tap **"Copy"**. *Save this token in your notes — this is your `DISCORD_BOT_TOKEN`!*
   - Scroll down to **"Privileged Gateway Intents"**:
     - Turn **ON** `Server Members Intent` (optional, helpful for staff checks).
     - Tap **"Save Changes"**.
4. Tap **"OAuth2"** $\rightarrow$ **"URL Generator"**:
   - Under **Scopes**, check: `bot` and `applications.commands`.
   - Under **Bot Permissions**, check:
     - `Send Messages`
     - `Create Public Threads`
     - `Create Private Threads`
     - `Send Messages in Threads`
     - `Manage Threads`
     - `Embed Links`
     - `Attach Files`
     - `Read Message History`
     - `Use Slash Commands`
5. Copy the generated invite URL at the bottom, paste it into your browser, and invite the bot to your Discord server!

---

### Step 2: Get Your Discord IDs (Turn on Developer Mode)

1. In the Discord app on your phone:
   - Tap your profile picture $\rightarrow$ **App Settings** $\rightarrow$ **Advanced** $\rightarrow$ Turn **ON** **Developer Mode**.
2. Copy the required IDs:
   - **Server ID (`GUILD_ID`)**: Tap the server name $\rightarrow$ scroll to bottom $\rightarrow$ **Copy Server ID**.
   - **Order Channel ID (`ORDER_CHANNEL_ID`)**: Long-press your public `#order-here` channel $\rightarrow$ **Copy Channel ID**.
   - **Staff Channel ID (`STAFF_CHANNEL_ID`)**: Long-press your private `#staff-orders` channel $\rightarrow$ **Copy Channel ID**.
   - **Staff Role ID (`STAFF_ROLE_ID`)**: Server Settings $\rightarrow$ Roles $\rightarrow$ tap your Staff role $\rightarrow$ tap the three dots $\rightarrow$ **Copy Role ID**.

---

### Step 3: Configure Your `.env` File

Copy `.env.example` to `.env` and paste your IDs:

```ini
DISCORD_BOT_TOKEN="your_copied_bot_token_here"
GUILD_ID="123456789012345678"
ORDER_CHANNEL_ID="123456789012345678"
STAFF_CHANNEL_ID="123456789012345678"
STAFF_ROLE_ID="123456789012345678"
ADMIN_ROLE_ID="123456789012345678"
DATABASE_PATH="data/blox_fruits.db"
CATALOG_PATH="data/catalog.json"
```

---

## ☁️ Zero-Cost & Low-Cost Hosting Options

### Option A: Railway (Recommended — Easy & Reliable)
1. Create a free account at [Railway.app](https://railway.app).
2. Connect your GitHub repository.
3. In Railway **Variables**, paste each variable from your `.env` file (`DISCORD_BOT_TOKEN`, `GUILD_ID`, etc.).
4. Add a **Persistent Volume**:
   - Go to your Railway service settings $\rightarrow$ **Volumes** $\rightarrow$ **Add Volume**.
   - Mount path: `/app/data`.
   - *This ensures your SQLite order database survives redeploys!*
5. Deploy! Railway will automatically install dependencies and start `bot.py`.

### Option B: Render (Background Worker)
1. Create an account at [Render.com](https://render.com).
2. Create a **New Background Worker** connected to your repository.
3. Environment: `Python 3`.
4. Build Command: `pip install -r requirements.txt`.
5. Start Command: `python bot.py`.
6. Add your environment variables in the Environment tab.

### Option C: Termux on Android Phone (100% Free & Local)
1. Install **Termux** from F-Droid.
2. Run:
   ```bash
   pkg update && pkg install python git
   git clone <your-repo-url>
   cd blox-fruit-bot
   pip install -r requirements.txt
   cp .env.example .env
   nano .env  # paste your token
   python bot.py
   ```

---

## 🎮 Slash Commands Manual

### Customer Commands
| Command | Description |
| :--- | :--- |
| `/order` | Open the interactive category and service booking menu. |
| `/catalog` | Browse published services and prices in Millions (M). |
| `/order-status <order_id>` | Check the current progress, upfront deposit, and balance of your own order. |
| `/help` | Explains bot features and rules. |

### Staff & Admin Commands
| Command | Permission | Description |
| :--- | :--- | :--- |
| `/setup` | Administrator | Sends the permanent **"🛒 Order Now"** embed to your order channel. |
| `/admin-order <order_id>` | Staff / Admin | Displays full order dossier, verified items received, and audit log. |
| `/edit-price <service_id> <price> [publish]` | Admin | Updates a service price or publishes a draft service. |
| `/order-history [limit]` | Staff / Admin | Lists the most recent customer orders and statuses. |

---

## 📋 Catalog Review Checklist (Draft Items Gated from Customers)

The following items are pre-configured in `data/catalog.json` with `"status": "draft"` and are **hidden from public ordering** until verified:

- [ ] **4 Trials (160M)**: Handwritten rate appears to be 160M. Verify if discounted or standard.
- [ ] **Other Materials (150K–1.5M)**: Wide variable range; verify specific drops or keep as custom staff quote.
- [ ] **Tyrant of the Skies (75M)**: Confirm 75M handwritten price.
- [ ] **Cyborg V1 (150M)**: Clarify if F.O.D. stands for *Fist of Darkness*.
- [ ] **V2 + V3 Bundle (35M–50M)**: Confirm fixed price.
- [ ] **Level 100**: Handwritten price was illegible; assign verified price.
- [ ] **PH & PH (with magnets) (50M/30M)**: Clarify abbreviation (Prehistoric Island / Leviathan Heart).
- [ ] **Dough Full Awakening (30M)**: Confirm microchip prerequisites with staff.
- [ ] **Low Raids (2.5M)**: Specify eligible basic raids (Flame, Ice, Sand, Light).
- [ ] **Raids to Core Break (70M)**: Clarify exact scope before publishing.
- [ ] **Dungeon Hard (50M)**: Confirm handwritten 50M rate.
- [ ] **10M Beli (45M)**: Confirm conversion rate.

To publish any draft item once confirmed, run:
`/edit-price service_id:<id> new_price_m:<price> publish:True`

---

## 🧪 Running Automated Tests

To run the automated test suite verifying calculations, rounding rules, database persistence, and staff authorization:

```bash
# Using Python standard runner:
python3 run_tests.py

# Or using pytest:
pytest tests/ -v
```
