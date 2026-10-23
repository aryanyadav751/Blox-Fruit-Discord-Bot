"""
Blox Fruit Services - Customer Ordering Cog.
Handles:
- Persistent "🛒 Order Now" button in #order-channel
- Slash command /order
- Ephemeral multi-step selection:
    1. Category select
    2. Service select
    3. Part 3A (Payment Plan: 50/50 vs One-Time Full)
    4. Part 3B (Payment Method: Fruits / Gamepasses / Combination)
    5. Order details Modal (Roblox username, timezone, proposed item offer)
    6. Confirmation summary card
- Unique persistent order ID generation (BFS-XXXX)
- SQLite order creation FIRST, then safe staff thread dispatch
- Resilient recovery if Discord thread or customer DM fails
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional
import json
import logging

from config import Config
from core.calculator import calculate_payment, format_m, PaymentPlan, PaymentMethod
from core.catalog import catalog, Category, Service
from core.database import db

logger = logging.getLogger("OrderingCog")


class OrderDetailsModal(discord.ui.Modal, title="Blox Fruit Services - Order Details"):
    roblox_username = discord.ui.TextInput(
        label="Your Roblox Username",
        placeholder="e.g. BloxMaster_99 (Do NOT share your password)",
        min_length=3,
        max_length=50,
        required=True,
    )

    availability = discord.ui.TextInput(
        label="Timezone & Available Play Hours",
        placeholder="e.g. UTC+5:30 (IST), Weekdays 6 PM - 10 PM",
        min_length=3,
        max_length=150,
        required=True,
    )

    proposed_offer = discord.ui.TextInput(
        label="Proposed Fruits / Gamepasses & Values",
        style=discord.TextStyle.paragraph,
        placeholder="List your items & estimated trade values (e.g. Dragon + Dough = ~110M)",
        min_length=3,
        max_length=500,
        required=True,
    )

    def __init__(
        self,
        category: Category,
        service: Service,
        plan: PaymentPlan,
        methods: List[PaymentMethod],
    ):
        super().__init__()
        self.category = category
        self.service = service
        self.plan = plan
        self.methods = methods

    async def on_submit(self, interaction: discord.Interaction):
        # Calculate payment breakdown using Decimal precision
        breakdown = calculate_payment(self.service.price_m, self.plan)

        # Show ephemeral confirmation card
        embed = discord.Embed(
            title="📋 Review Your Order Summary",
            description=(
                f"Please review your booking details before submitting.\n"
                f"**Note:** Prices represent in-game trade value in **Millions (M)**. "
                f"No real-world money is accepted."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Selected Service", value=f"**{self.service.name}** ({self.category.name})", inline=False)
        embed.add_field(name="Total Value", value=f"**{format_m(breakdown.total_price_m)}** estimated trade value", inline=True)
        embed.add_field(name="Payment Plan", value=f"**{self.plan.label}**", inline=True)

        if self.plan == PaymentPlan.SPLIT_50_50:
            embed.add_field(name="Upfront Deposit (50%)", value=f"**{format_m(breakdown.initial_payment_m)}**", inline=True)
            embed.add_field(name="Remaining Balance (50%)", value=f"**{format_m(breakdown.remaining_balance_m)}**", inline=True)
        else:
            embed.add_field(name="Full Upfront Due", value=f"**{format_m(breakdown.initial_payment_m)}**", inline=True)
            embed.add_field(name="Remaining Balance", value="**0M (None)**", inline=True)

        method_labels = ", ".join([m.label for m in self.methods])
        embed.add_field(name="Payment Methods", value=method_labels, inline=False)
        embed.add_field(name="Roblox Username", value=f"`{self.roblox_username.value}`", inline=True)
        embed.add_field(name="Timezone / Availability", value=self.availability.value, inline=True)
        embed.add_field(name="Proposed Offer Breakdown", value=f"```{self.proposed_offer.value}```", inline=False)
        embed.set_footer(text="Staff will verify items in Roblox before crediting your deposit.")

        view = OrderConfirmationView(
            category=self.category,
            service=self.service,
            plan=self.plan,
            methods=self.methods,
            roblox_username=self.roblox_username.value,
            availability=self.availability.value,
            proposed_offer=self.proposed_offer.value,
            breakdown=breakdown,
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class OrderConfirmationView(discord.ui.View):
    def __init__(
        self,
        category: Category,
        service: Service,
        plan: PaymentPlan,
        methods: List[PaymentMethod],
        roblox_username: str,
        availability: str,
        proposed_offer: str,
        breakdown,
    ):
        super().__init__(timeout=300)
        self.category = category
        self.service = service
        self.plan = plan
        self.methods = methods
        self.roblox_username = roblox_username
        self.availability = availability
        self.proposed_offer = proposed_offer
        self.breakdown = breakdown
        self.submitted = False

    @discord.ui.button(label="Confirm & Submit Order", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.submitted:
            await interaction.response.send_message("This order has already been submitted.", ephemeral=True)
            return

        self.submitted = True
        self.stop()

        await interaction.response.defer(ephemeral=True)

        # 1. Generate unique persistent Order ID (e.g. BFS-1042)
        order_id = await db.get_next_order_id()

        # 2. Save order to SQLite FIRST so order is NEVER lost even if Discord calls fail
        method_str = json.dumps([m.value for m in self.methods])
        await db.create_order(
            order_id=order_id,
            customer_id=interaction.user.id,
            customer_tag=str(interaction.user),
            roblox_username=self.roblox_username,
            category_id=self.category.id,
            service_id=self.service.id,
            service_name=self.service.name,
            total_price_m=self.breakdown.total_price_m,
            payment_plan=self.plan.value,
            initial_payment_required_m=self.breakdown.initial_payment_m,
            balance_remaining_m=self.breakdown.remaining_balance_m,
            payment_methods=method_str,
            proposed_items=self.proposed_offer,
            customer_availability=self.availability,
            status="PENDING_ACCEPTANCE",
        )

        # 3. Post to Staff Channel & spawn private thread
        bot = interaction.client
        staff_channel_id = Config.STAFF_CHANNEL_ID
        staff_channel = bot.get_channel(staff_channel_id) if staff_channel_id else None

        thread = None
        staff_msg = None

        if staff_channel and isinstance(staff_channel, (discord.TextChannel, discord.ForumChannel)):
            staff_embed = discord.Embed(
                title=f"📦 New Order: `{order_id}` — {self.service.name}",
                description=f"A new service request has been placed by {interaction.user.mention}.",
                color=discord.Color.blue(),
            )
            staff_embed.add_field(name="Customer", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
            staff_embed.add_field(name="Roblox Username", value=f"`{self.roblox_username}`", inline=True)
            staff_embed.add_field(name="Service", value=f"**{self.service.name}**\nCategory: {self.category.name}", inline=True)
            staff_embed.add_field(name="Total Value", value=f"**{format_m(self.breakdown.total_price_m)}**", inline=True)
            staff_embed.add_field(name="Payment Plan", value=f"**{self.plan.label}**", inline=True)

            if self.plan == PaymentPlan.SPLIT_50_50:
                staff_embed.add_field(
                    name="Split (50/50)",
                    value=f"Upfront Due: **{format_m(self.breakdown.initial_payment_m)}**\nRemaining: **{format_m(self.breakdown.remaining_balance_m)}**",
                    inline=True,
                )
            else:
                staff_embed.add_field(
                    name="Upfront (100%)",
                    value=f"Full Due: **{format_m(self.breakdown.initial_payment_m)}**\nRemaining: **0M**",
                    inline=True,
                )

            methods_text = ", ".join([m.label for m in self.methods])
            staff_embed.add_field(name="Payment Methods", value=methods_text, inline=False)
            staff_embed.add_field(name="Availability", value=self.availability, inline=True)
            staff_embed.add_field(name="Status", value="⏳ `PENDING_ACCEPTANCE`", inline=True)
            staff_embed.add_field(name="Customer Proposed Offer", value=f"```{self.proposed_offer}```", inline=False)

            try:
                from cogs.staff_controls import StaffOrderThreadView

                staff_view = StaffOrderThreadView(order_id=order_id, plan=self.plan)
                staff_msg = await staff_channel.send(embed=staff_embed)

                # Attempt private thread creation
                thread_name = f"order-{order_id.lower()}"
                try:
                    thread = await staff_msg.create_thread(
                        name=thread_name,
                        auto_archive_duration=1440,
                    )
                except Exception as thread_err:
                    logger.warning("Could not create thread on message: %s. Attempting fallback.", thread_err)
                    try:
                        thread = await staff_channel.create_thread(
                            name=thread_name,
                            type=discord.ChannelType.private_thread,
                            auto_archive_duration=1440,
                        )
                    except Exception as private_err:
                        logger.error("Could not create private thread (%s). Attaching controls directly to message.", private_err)

                if thread:
                    await thread.send(
                        content=f"🔔 Staff notification for order `{order_id}`. Use the controls below to manage this order.",
                        embed=staff_embed,
                        view=staff_view,
                    )
                    await db.set_thread_and_message(order_id, thread.id, staff_msg.id)
                else:
                    # Fallback: attach controls to main staff message
                    await staff_msg.edit(view=staff_view)
                    await db.set_thread_and_message(order_id, 0, staff_msg.id)
            except Exception as e:
                logger.error("Failed to post staff channel message: %s", e)
        else:
            logger.warning("Staff channel (ID: %s) not configured or not accessible.", staff_channel_id)

        # 4. DM customer
        dm_sent = True
        dm_embed = discord.Embed(
            title=f"🎉 Order Received: `{order_id}`",
            description=(
                f"Thank you for ordering with **Blox Fruit Services**!\n"
                f"Your order `{order_id}` has been safely recorded and forwarded to our staff team."
            ),
            color=discord.Color.green(),
        )
        dm_embed.add_field(name="Service", value=self.service.name, inline=True)
        dm_embed.add_field(name="Total Value", value=f"{format_m(self.breakdown.total_price_m)}", inline=True)
        dm_embed.add_field(name="Payment Plan", value=self.plan.label, inline=False)

        if self.plan == PaymentPlan.SPLIT_50_50:
            dm_embed.add_field(name="Upfront Deposit Due", value=f"**{format_m(self.breakdown.initial_payment_m)}**", inline=True)
            dm_embed.add_field(name="Remaining on Completion", value=f"**{format_m(self.breakdown.remaining_balance_m)}**", inline=True)
        else:
            dm_embed.add_field(name="Upfront Due", value=f"**{format_m(self.breakdown.initial_payment_m)}**", inline=True)

        dm_embed.add_field(
            name="Next Steps",
            value=(
                "1. An authorized staff member will review your proposed items.\n"
                "2. Once accepted, staff will coordinate the in-game trade with your Roblox account (`"
                + self.roblox_username
                + "`).\n"
                "3. **Never share passwords or authentication codes with anyone!**"
            ),
            inline=False,
        )

        try:
            await interaction.user.send(embed=dm_embed)
        except (discord.Forbidden, discord.HTTPException):
            dm_sent = False
            if thread:
                await thread.send(f"⚠️ **Note:** Customer {interaction.user.mention} has direct messages (DMs) disabled.")

        # 5. Ephemeral reply
        success_msg = f"✅ Your order **`{order_id}`** has been successfully placed!"
        if not dm_sent:
            success_msg += "\n⚠️ *Your Discord DMs appear to be closed. Please enable DMs or contact staff with your Order ID.*"
        else:
            success_msg += "\n📬 A confirmation message has been sent to your Direct Messages (DMs)."

        await interaction.followup.send(success_msg, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey, emoji="❌")
    async def cancel_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("❌ Order cancelled. No booking was created.", ephemeral=True)


class PaymentPreferenceView(discord.ui.View):
    def __init__(self, category: Category, service: Service):
        super().__init__(timeout=180)
        self.category = category
        self.service = service
        self.selected_plan: PaymentPlan = PaymentPlan.SPLIT_50_50
        self.selected_methods: List[PaymentMethod] = [PaymentMethod.FRUITS]

    @discord.ui.select(
        placeholder="Part 3A: Select Payment Plan (50/50 or Full)",
        options=[
            discord.SelectOption(
                label="50/50 Payment (50% Upfront, 50% on Completion)",
                value="SPLIT_50_50",
                description="Pay half deposit upfront, pay the other half upon service finish.",
                default=True,
                emoji="⚖️",
            ),
            discord.SelectOption(
                label="One-Time Full Payment (100% Upfront)",
                value="FULL_UPFRONT",
                description="Pay 100% upfront with zero remaining balance.",
                emoji="💰",
            ),
        ],
    )
    async def select_plan(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_plan = PaymentPlan(select.values[0])
        for opt in select.options:
            opt.default = opt.value == select.values[0]
        await interaction.response.edit_message(view=self)

    @discord.ui.select(
        placeholder="Part 3B: Select In-Game Payment Items",
        min_values=1,
        max_values=3,
        options=[
            discord.SelectOption(
                label="🍎 Fruits Only",
                value="FRUITS",
                description="Pay using in-game physical/stored fruits (e.g. Dragon, Dough, Leopard)",
                default=True,
            ),
            discord.SelectOption(
                label="🎟️ Gamepasses Only",
                value="GAMEPASSES",
                description="Pay using gifted/traded Gamepasses (e.g. 2x Mastery, +1 Fruit Storage)",
            ),
            discord.SelectOption(
                label="🍎+🎟️ Combination (Fruits & Gamepasses)",
                value="COMBINATION",
                description="Mix multiple fruits and gamepasses to reach the agreed value.",
            ),
        ],
    )
    async def select_methods(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_methods = [PaymentMethod(val) for val in select.values]
        for opt in select.options:
            opt.default = opt.value in select.values
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Next: Enter Order Details", style=discord.ButtonStyle.primary, emoji="➡️")
    async def proceed_to_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = OrderDetailsModal(
            category=self.category,
            service=self.service,
            plan=self.selected_plan,
            methods=self.selected_methods,
        )
        await interaction.response.send_modal(modal)


class ServiceSelectView(discord.ui.View):
    def __init__(self, category: Category):
        super().__init__(timeout=180)
        self.category = category

        services = category.active_services()
        options = [
            discord.SelectOption(
                label=f"{s.name} ({format_m(s.price_m)})",
                value=s.id,
                description=s.description[:95] if s.description else "No description",
            )
            for s in services[:25]
        ]

        self.service_select = discord.ui.Select(
            placeholder="Step 2: Select a service...",
            options=options,
        )
        self.service_select.callback = self.on_service_select
        self.add_item(self.service_select)

    async def on_service_select(self, interaction: discord.Interaction):
        service_id = self.service_select.values[0]
        service = catalog.get_service(service_id)
        if not service:
            await interaction.response.send_message("Service not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Service: {service.name}",
            description=service.description or "No description provided.",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Category", value=self.category.name, inline=True)
        embed.add_field(name="Estimated Trade Value", value=f"**{format_m(service.price_m)}**", inline=True)
        if service.prerequisites:
            embed.add_field(name="Prerequisites", value=service.prerequisites, inline=False)

        embed.add_field(
            name="Payment Options Available",
            value=(
                "• **50/50 Split**: Pay 50% deposit upfront, 50% remaining upon completion.\n"
                "• **One-Time Full**: Pay 100% upfront.\n"
                "• **Methods**: Fruits, Gamepasses, or Combinations."
            ),
            inline=False,
        )

        view = PaymentPreferenceView(category=self.category, service=service)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CategorySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        categories = catalog.get_active_categories()
        options = [
            discord.SelectOption(
                label=cat.name,
                value=cat.id,
                description=cat.description[:95] if cat.description else "Services in this category",
            )
            for cat in categories[:25]
        ]

        self.cat_select = discord.ui.Select(
            placeholder="Step 1: Choose a service category...",
            options=options,
        )
        self.cat_select.callback = self.on_category_select
        self.add_item(self.cat_select)

    async def on_category_select(self, interaction: discord.Interaction):
        cat_id = self.cat_select.values[0]
        category = catalog.categories.get(cat_id)
        if not category:
            await interaction.response.send_message("Category not found.", ephemeral=True)
            return

        view = ServiceSelectView(category=category)
        await interaction.response.send_message(
            f"You selected **{category.name}**. Now choose the service you want:",
            view=view,
            ephemeral=True,
        )


class PublicOrderPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Order Now",
        style=discord.ButtonStyle.green,
        emoji="🛒",
        custom_id="bfs_public_order_now_button",
    )
    async def order_now_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CategorySelectView()
        await interaction.response.send_message(
            "Welcome to **Blox Fruit Services**! Choose a category below to start your order:",
            view=view,
            ephemeral=True,
        )


class OrderingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="order", description="Start placing a Blox Fruit service booking order")
    async def order_command(self, interaction: discord.Interaction):
        view = CategorySelectView()
        await interaction.response.send_message(
            "Welcome to **Blox Fruit Services**! Choose a category below to start your order:",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OrderingCog(bot))
