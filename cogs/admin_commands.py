"""
Blox Fruit Services - Admin & General Slash Commands Cog.
Implements:
- /setup: Deploy public order panel and verify channels/roles
- /catalog: View published in-game service prices in M
- /order-status: Customer lookup of their own order
- /admin-order: Staff inspection of an order, payment records, and audit log
- /edit-price: Authorized administrator price and draft management
- /order-history: Staff overview of recent orders
- /help: Detailed customer and staff command manual
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from config import Config
from core.calculator import format_m
from core.catalog import catalog
from core.database import db
from core.permissions import is_staff
from cogs.ordering import PublicOrderPanelView


class AdminCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Deploy the persistent 'Order Now' panel to the order channel")
    @app_commands.default_permissions(administrator=True)
    async def setup_command(
        self,
        interaction: discord.Interaction,
        order_channel: Optional[discord.TextChannel] = None,
        staff_channel: Optional[discord.TextChannel] = None,
        staff_role: Optional[discord.Role] = None,
    ):
        """Admin command to configure and send the Order Now embed."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("⛔ You must be a server Administrator to run /setup.", ephemeral=True)
            return

        target_order_channel = order_channel or interaction.client.get_channel(Config.ORDER_CHANNEL_ID) or interaction.channel
        if not isinstance(target_order_channel, discord.TextChannel):
            await interaction.response.send_message("❌ Target order channel must be a text channel.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚔️ Blox Fruit Services — Service Booking ⚔️",
            description=(
                "Welcome to **Blox Fruit Services**!\n\n"
                "We provide safe, reliable in-game assistance and carries for **Blox Fruits**:\n"
                "• **Trials (V4 Awakening)**: 1 to 5 trials carry\n"
                "• **Bosses**: Dough King, Cake Prince, Darkbeard\n"
                "• **Swords**: True Triple Katana (TTK), Shark Anchor, Yama, Rengoku\n"
                "• **Progression**: V2/V3 Race, Bartilo, Belts, Soul Guitar\n"
                "• **Sea Events**: Kitsune Shrine, Leviathan, Mirage & Blue Gear\n"
                "• **Raids & Dungeons**: Full Awakenings, Fragment Raids\n\n"
                "📌 **Payment Rules & In-Game Currency:**\n"
                "• All prices are in **estimated in-game trade value (M)**.\n"
                "• **NO REAL-WORLD MONEY** (No USD/INR/bank transfers).\n"
                "• Pay using **Physical Fruits**, **Gamepasses**, or a **Combination**.\n"
                "• Choose **50/50 Split** (half upfront, half on completion) or **One-Time Full**.\n"
                "• **Never share your Roblox password or login credentials with anyone!**\n\n"
                "Click the button below to browse categories and place your booking!"
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=256&q=80")
        embed.set_footer(text="Blox Fruit Services • Trusted In-Game Carries")

        view = PublicOrderPanelView()
        await target_order_channel.send(embed=embed, view=view)

        summary = f"✅ Sent persistent **Order Now** panel to {target_order_channel.mention}!"
        if staff_channel:
            summary += f"\nStaff Channel: {staff_channel.mention}"
        if staff_role:
            summary += f"\nStaff Role: {staff_role.mention}"

        await interaction.response.send_message(summary, ephemeral=True)

    @app_commands.command(name="catalog", description="Browse active Blox Fruit services and estimated prices in M")
    async def catalog_command(self, interaction: discord.Interaction):
        categories = catalog.get_active_categories()
        embed = discord.Embed(
            title="📜 Blox Fruit Services — Price Catalog",
            description=(
                "All prices are estimated in-game trade value in **Millions (M)**.\n"
                "Payment accepted in fruits and gamepasses.\n"
                "Choose 50/50 payment (half upfront) or One-Time Full upfront."
            ),
            color=discord.Color.blue(),
        )

        for cat in categories:
            lines = []
            for s in cat.active_services():
                half_price = round(s.price_m / 2.0, 2)
                lines.append(f"• **{s.name}** — `{format_m(s.price_m)}` *(50% deposit: {format_m(half_price)})*")
            if lines:
                embed.add_field(name=f"🔹 {cat.name}", value="\n".join(lines[:10]), inline=False)

        embed.set_footer(text="Run /order or click 'Order Now' in the order channel to book.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="order-status", description="Look up the status and balance of your own order")
    @app_commands.describe(order_id="Your order ID (e.g. BFS-1001)")
    async def order_status_command(self, interaction: discord.Interaction, order_id: str):
        order = await db.get_order(order_id.strip().upper())
        if not order:
            await interaction.response.send_message(f"❌ Order `{order_id}` not found.", ephemeral=True)
            return

        # Restrict customer to their own order unless staff
        caller = interaction.user
        if order["customer_id"] != caller.id and not (isinstance(caller, discord.Member) and is_staff(caller)):
            await interaction.response.send_message("⛔ You may only look up your own orders.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 Order Status: `{order['order_id']}`",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Service", value=order["service_name"], inline=True)
        embed.add_field(name="Status", value=f"`{order['status']}`", inline=True)
        embed.add_field(name="Total Value", value=f"**{format_m(order['total_price_m'])}**", inline=True)
        embed.add_field(name="Payment Plan", value=order["payment_plan"], inline=True)
        embed.add_field(name="Initial Upfront Paid", value=f"{format_m(order['initial_payment_paid_m'])} / {format_m(order['initial_payment_required_m'])}", inline=True)
        embed.add_field(name="Balance Remaining", value=f"{format_m(order['balance_remaining_m'])}", inline=True)
        embed.add_field(name="Roblox Username", value=f"`{order['roblox_username']}`", inline=True)
        embed.add_field(name="Created At", value=order["created_at"], inline=True)

        if order.get("cancellation_reason"):
            embed.add_field(name="Cancellation Reason", value=order["cancellation_reason"], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="admin-order", description="Staff lookup of an order with full payment and audit records")
    @app_commands.describe(order_id="Order ID (e.g. BFS-1001)")
    async def admin_order_command(self, interaction: discord.Interaction, order_id: str):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Staff authorization required.", ephemeral=True)
            return

        order = await db.get_order(order_id.strip().upper())
        if not order:
            await interaction.response.send_message(f"❌ Order `{order_id}` not found.", ephemeral=True)
            return

        payments = await db.get_order_payments(order["order_id"])
        audits = await db.get_order_audits(order["order_id"])

        embed = discord.Embed(
            title=f"🛡️ Staff Order Dossier: `{order['order_id']}`",
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="Customer", value=f"<@{order['customer_id']}> (`{order['customer_tag']}`)", inline=True)
        embed.add_field(name="Roblox Username", value=f"`{order['roblox_username']}`", inline=True)
        embed.add_field(name="Service", value=f"**{order['service_name']}**", inline=True)
        embed.add_field(name="Status", value=f"`{order['status']}`", inline=True)
        embed.add_field(name="Total Price", value=f"**{format_m(order['total_price_m'])}**", inline=True)
        embed.add_field(name="Payment Plan", value=order["payment_plan"], inline=True)
        embed.add_field(
            name="Payment Breakdown",
            value=(
                f"Upfront Req: **{format_m(order['initial_payment_required_m'])}** (Paid: {format_m(order['initial_payment_paid_m'])})\n"
                f"Balance Rem: **{format_m(order['balance_remaining_m'])}** (Paid: {format_m(order['balance_paid_m'])})"
            ),
            inline=False,
        )
        embed.add_field(name="Customer Offer", value=f"```{order['proposed_items']}```", inline=False)
        embed.add_field(name="Availability", value=order["customer_availability"], inline=False)

        # Payment records list
        if payments:
            pay_lines = [
                f"• `{p['recorded_at']}` | **{p['payment_stage']}**: {format_m(p['credited_value_m'])} "
                f"({p['items_received']}) by {p['verified_by_staff_tag']}"
                for p in payments
            ]
            embed.add_field(name="💰 Verified Payments", value="\n".join(pay_lines[:5]), inline=False)
        else:
            embed.add_field(name="💰 Verified Payments", value="*No payments verified yet.*", inline=False)

        # Recent audit logs
        if audits:
            audit_lines = [
                f"• `{a['created_at']}`: **{a['action']}** by {a['actor_tag']} ({a['details'][:60]})"
                for a in audits[-5:]
            ]
            embed.add_field(name="📜 Recent Audit Events", value="\n".join(audit_lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="edit-price", description="Authorized admin update of a service price or draft publishing")
    @app_commands.describe(
        service_id="Service ID from catalog (e.g. trials_4, dungeon_hard)",
        new_price_m="New price in estimated trade value Millions (M)",
        publish="Set to True to publish an unconfirmed draft service",
    )
    async def edit_price_command(
        self,
        interaction: discord.Interaction,
        service_id: str,
        new_price_m: float,
        publish: bool = False,
    ):
        if not isinstance(interaction.user, discord.Member) or not (
            interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message("⛔ Administrator permissions required to edit prices.", ephemeral=True)
            return

        service = catalog.get_service(service_id.strip())
        if not service:
            await interaction.response.send_message(f"❌ Service ID `{service_id}` not found in catalog.", ephemeral=True)
            return

        old_price = service.price_m
        old_status = service.status
        success = catalog.update_price(service.id, new_price_m, activate=publish)

        if success:
            msg = f"✅ Updated **{service.name}** (`{service.id}`):\n"
            msg += f"• Price: `{format_m(old_price)}` ➡️ **`{format_m(new_price_m)}`**\n"
            if publish:
                msg += f"• Status: `{old_status}` ➡️ **`active` (Published!)**"
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to update service.", ephemeral=True)

    @app_commands.command(name="order-history", description="Staff overview of recent orders")
    @app_commands.describe(limit="Number of recent orders to display (1 to 25)")
    async def order_history_command(self, interaction: discord.Interaction, limit: int = 10):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Staff authorization required.", ephemeral=True)
            return

        limit = max(1, min(limit, 25))
        orders = await db.get_recent_orders(limit=limit)

        if not orders:
            await interaction.response.send_message("No orders found in database.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 Recent Orders (Last {len(orders)})",
            color=discord.Color.dark_purple(),
        )

        for o in orders:
            embed.add_field(
                name=f"`{o['order_id']}` — {o['service_name']} ({format_m(o['total_price_m'])})",
                value=(
                    f"Customer: <@{o['customer_id']}> | Status: `{o['status']}`\n"
                    f"Plan: `{o['payment_plan']}` | Created: `{o['created_at'][:16]}`"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Guide for Blox Fruit Services booking bot")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Blox Fruit Services — Help & Commands",
            description=(
                "**Blox Fruit Services** connects customers with trusted in-game carries and services. "
                "All transactions use in-game Blox Fruits trade value measured in **Millions (M)**. "
                "No real-world money is accepted.\n"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="🛒 Customer Commands",
            value=(
                "• `/order` — Start ordering a service.\n"
                "• `/catalog` — View all active services, prices, and 50% deposits.\n"
                "• `/order-status <order_id>` — Check progress and balance of your own booking.\n"
                "• Or click the **Order Now** button in the order channel!"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Staff & Admin Commands",
            value=(
                "• `/setup` — Deploy the persistent Order Now panel (Admin only).\n"
                "• `/admin-order <order_id>` — View full order details, payments, and audits.\n"
                "• `/edit-price <id> <price> [publish]` — Modify price or publish draft services.\n"
                "• `/order-history [limit]` — View recent customer orders."
            ),
            inline=False,
        )
        embed.add_field(
            name="🔒 Security Reminder",
            value="Staff will NEVER ask for your Roblox password, security cookies, or email codes.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommandsCog(bot))
