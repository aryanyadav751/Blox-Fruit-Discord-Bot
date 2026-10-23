"""
Blox Fruit Services - Staff Controls & Thread Management Cog.
Handles:
- Server-side authorization checks for staff and admin roles across views and modals
- Interactive buttons inside private order threads (#order-bfs-xxxx)
- Payment verification modals (Upfront deposit vs Remaining balance)
- State machine transition enforcement and over-crediting prevention
- Real-time customer DMs upon status transitions (with blocked DM resilience)
- Comprehensive audit trails and persistent order updates
"""

import discord
from discord.ext import commands
from typing import Optional, Dict, Any
from decimal import Decimal

from config import Config
from core.calculator import format_m, PaymentPlan, to_decimal
from core.database import db


def is_staff(member: Any) -> bool:
    """Server-side authorization check for staff/admin permissions."""
    if not member or not hasattr(member, "guild_permissions"):
        return False
    perms = member.guild_permissions
    if getattr(perms, "administrator", False) or getattr(perms, "manage_guild", False):
        return True
    staff_role_id = Config.STAFF_ROLE_ID
    admin_role_id = Config.ADMIN_ROLE_ID
    user_role_ids = [getattr(r, "id", None) for r in getattr(member, "roles", [])]
    return bool((staff_role_id and staff_role_id in user_role_ids) or (admin_role_id and admin_role_id in user_role_ids))


async def send_customer_dm(bot: discord.Client, customer_id: int, embed: discord.Embed) -> bool:
    """Attempts to DM the customer, returns True if sent, False if DMs blocked."""
    try:
        user = bot.get_user(customer_id) or await bot.fetch_user(customer_id)
        if user:
            await user.send(embed=embed)
            return True
    except (discord.Forbidden, discord.HTTPException):
        pass
    return False


class RecordPaymentModal(discord.ui.Modal):
    items_received = discord.ui.TextInput(
        label="Items Received in Trade",
        placeholder="e.g. 1x Dragon, 1x Dough (or 2x Mastery)",
        min_length=2,
        max_length=200,
        required=True,
    )

    credited_value_m = discord.ui.TextInput(
        label="Agreed Trade Value Credited (in M)",
        placeholder="e.g. 75.0 (Numbers only)",
        min_length=1,
        max_length=20,
        required=True,
    )

    notes = discord.ui.TextInput(
        label="Staff Notes (Optional)",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. Traded in Second Sea cafe at 8:15 PM UTC",
        required=False,
        max_length=300,
    )

    def __init__(self, order_id: str, stage: str, parent_view: "StaffOrderThreadView"):
        stage_label = "Upfront Deposit" if stage == "UPFRONT" else "Remaining Balance"
        super().__init__(title=f"Record {stage_label} - {order_id}")
        self.order_id = order_id
        self.stage = stage
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        # Strict server-side authorization check inside modal callback
        if not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Unauthorized: Staff permissions required.", ephemeral=True)
            return

        # Validate credited value
        try:
            val_str = self.credited_value_m.value.strip().replace("M", "").replace("m", "")
            val_dec = to_decimal(val_str)
            if val_dec <= Decimal("0"):
                raise ValueError()
        except Exception:
            await interaction.response.send_message("❌ Invalid amount. Please enter a positive number in M.", ephemeral=True)
            return

        await interaction.response.defer()

        # Update database with state and over-crediting validation
        try:
            updated_order = await db.record_payment(
                order_id=self.order_id,
                payment_stage=self.stage,
                items_received=self.items_received.value.strip(),
                credited_value_m=val_dec,
                staff_id=interaction.user.id,
                staff_tag=str(interaction.user),
                notes=self.notes.value.strip() if self.notes.value else "",
            )
        except ValueError as err:
            await interaction.followup.send(f"❌ Payment verification rejected: {err}", ephemeral=True)
            return

        # Notify thread
        stage_title = "Upfront Deposit" if self.stage == "UPFRONT" else "Final Balance"
        payment_embed = discord.Embed(
            title=f"💰 Payment Verified: {stage_title}",
            description=f"Staff member {interaction.user.mention} recorded verified payment for `{self.order_id}`.",
            color=discord.Color.green(),
        )
        payment_embed.add_field(name="Items Received", value=f"`{self.items_received.value}`", inline=False)
        payment_embed.add_field(name="Credited Value", value=f"**{format_m(val_dec)}**", inline=True)
        payment_embed.add_field(name="Total Initial Paid", value=f"{format_m(updated_order['initial_payment_paid_m'])}", inline=True)
        payment_embed.add_field(name="Total Balance Paid", value=f"{format_m(updated_order['balance_paid_m'])}", inline=True)
        payment_embed.add_field(name="New Status", value=f"`{updated_order['status']}`", inline=True)
        if self.notes.value:
            payment_embed.add_field(name="Notes", value=self.notes.value, inline=False)

        await interaction.channel.send(embed=payment_embed)

        # DM customer
        customer_embed = discord.Embed(
            title=f"💰 Payment Verified for Order `{self.order_id}`",
            description=(
                f"Your payment of **{format_m(val_dec)}** ({self.items_received.value}) has been verified by staff!\n"
                f"**Service:** {updated_order['service_name']}"
            ),
            color=discord.Color.green(),
        )
        customer_embed.add_field(name="Status", value=f"`{updated_order['status']}`", inline=True)
        dm_ok = await send_customer_dm(interaction.client, updated_order["customer_id"], customer_embed)
        if not dm_ok:
            await interaction.channel.send(f"⚠️ Note: Customer DMs are closed. Could not send payment receipt DM.")

        await interaction.followup.send(f"✅ Verified {stage_title} for `{self.order_id}`.", ephemeral=True)


class RequestInfoModal(discord.ui.Modal):
    message_text = discord.ui.TextInput(
        label="Message to Customer",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. Please clarify your second fruit offer or when you will be online...",
        min_length=5,
        max_length=500,
        required=True,
    )

    def __init__(self, order_id: str):
        super().__init__(title=f"Request Info - {order_id}")
        self.order_id = order_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Unauthorized: Staff permissions required.", ephemeral=True)
            return

        order = await db.get_order(self.order_id)
        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        await interaction.response.defer()

        # Send DM to customer
        dm_embed = discord.Embed(
            title=f"❓ Message from Blox Fruit Services Staff (`{self.order_id}`)",
            description=f"Staff member **{interaction.user.display_name}** has requested more information regarding your order:",
            color=discord.Color.orange(),
        )
        dm_embed.add_field(name="Staff Message", value=f"```{self.message_text.value}```", inline=False)
        dm_embed.add_field(name="How to respond", value="Please reply directly to staff or message an authorized staff member.", inline=False)

        dm_ok = await send_customer_dm(interaction.client, order["customer_id"], dm_embed)

        # Log in thread
        thread_embed = discord.Embed(
            title=f"📨 Staff Requested Information (`{self.order_id}`)",
            description=f"Sent by {interaction.user.mention} to <@{order['customer_id']}>",
            color=discord.Color.orange(),
        )
        thread_embed.add_field(name="Message Sent", value=self.message_text.value, inline=False)
        if not dm_ok:
            thread_embed.add_field(name="DM Status", value="❌ Failed (Customer DMs are closed)", inline=False)

        await interaction.channel.send(embed=thread_embed)
        await db.update_order_status(
            order_id=self.order_id,
            new_status=order["status"],
            actor_id=interaction.user.id,
            actor_tag=str(interaction.user),
            details=f"Requested info: {self.message_text.value}",
            force=True,
        )
        await interaction.followup.send("✅ Info request dispatched to customer.", ephemeral=True)


class CancelOrderModal(discord.ui.Modal):
    reason = discord.ui.TextInput(
        label="Cancellation / Rejection Reason",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. Customer requested cancellation / Incompatible level / Unreachable",
        min_length=5,
        max_length=300,
        required=True,
    )

    def __init__(self, order_id: str):
        super().__init__(title=f"Cancel Order - {order_id}")
        self.order_id = order_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Unauthorized: Staff permissions required.", ephemeral=True)
            return

        order = await db.get_order(self.order_id)
        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            updated_order = await db.cancel_order(
                order_id=self.order_id,
                actor_id=interaction.user.id,
                actor_tag=str(interaction.user),
                reason=self.reason.value.strip(),
                is_rejection=(order["status"] == "PENDING_ACCEPTANCE"),
            )
        except ValueError as err:
            await interaction.followup.send(f"❌ Cannot cancel: {err}", ephemeral=True)
            return

        # Notify thread
        cancel_embed = discord.Embed(
            title=f"🛑 Order {updated_order['status']}: `{self.order_id}`",
            description=f"Action by {interaction.user.mention}\n**Reason:** {self.reason.value.strip()}",
            color=discord.Color.red(),
        )
        await interaction.channel.send(embed=cancel_embed)

        # DM customer
        dm_embed = discord.Embed(
            title=f"Order {updated_order['status'].capitalize()}: `{self.order_id}`",
            description=f"Your order for **{order['service_name']}** has been {updated_order['status'].lower()}.",
            color=discord.Color.red(),
        )
        dm_embed.add_field(name="Reason", value=self.reason.value.strip(), inline=False)
        dm_ok = await send_customer_dm(interaction.client, order["customer_id"], dm_embed)
        if not dm_ok:
            await interaction.channel.send("⚠️ Customer DMs are closed. Cancellation DM not delivered.")

        await interaction.followup.send(f"✅ Order `{self.order_id}` marked as {updated_order['status']}.", ephemeral=True)


class StaffOrderThreadView(discord.ui.View):
    """
    Persistent staff view inside order threads.
    Buttons adapt based on the order's payment plan (50/50 vs One-Time Full).
    """

    def __init__(self, order_id: str, plan: PaymentPlan = PaymentPlan.SPLIT_50_50):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.plan = plan

        # Set custom IDs for persistent registration across bot restarts
        self.accept_button.custom_id = f"bfs_accept_{order_id}"
        self.record_deposit_button.custom_id = f"bfs_record_deposit_{order_id}"
        self.start_service_button.custom_id = f"bfs_start_{order_id}"
        self.mark_completed_button.custom_id = f"bfs_completed_{order_id}"
        self.record_balance_button.custom_id = f"bfs_record_balance_{order_id}"
        self.request_info_button.custom_id = f"bfs_req_info_{order_id}"
        self.cancel_button.custom_id = f"bfs_cancel_{order_id}"

        # If one-time full upfront, hide the balance recording button
        if plan == PaymentPlan.FULL_UPFRONT:
            self.remove_item(self.record_balance_button)
            self.record_deposit_button.label = "Record Full Upfront Payment"
            self.mark_completed_button.label = "Complete & Close Order"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "⛔ Unauthorized: Only authorized Blox Fruit Services staff may use these controls.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Accept Order", style=discord.ButtonStyle.green, emoji="✅", row=0)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        order = await db.get_order(self.order_id)
        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        await interaction.response.defer()

        new_status = "AWAITING_UPFRONT_PAYMENT"
        try:
            await db.update_order_status(
                order_id=self.order_id,
                new_status=new_status,
                actor_id=interaction.user.id,
                actor_tag=str(interaction.user),
                details="Staff accepted order and initiated payment coordination",
                assigned_staff_id=interaction.user.id,
            )
        except ValueError as err:
            await interaction.followup.send(f"❌ Cannot accept order: {err}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"✅ Order Accepted: `{self.order_id}`",
            description=f"Staff member {interaction.user.mention} accepted this order and will handle service fulfillment.",
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=embed)

        # DM customer
        dm_embed = discord.Embed(
            title=f"✅ Order Accepted: `{self.order_id}`",
            description=(
                f"Great news! Your order for **{order['service_name']}** has been accepted by our staff team!\n"
                f"Assigned Staff: **{interaction.user.display_name}**"
            ),
            color=discord.Color.green(),
        )
        dm_embed.add_field(
            name="Payment Required Upfront",
            value=f"**{format_m(order['initial_payment_required_m'])}** estimated trade value.",
            inline=False,
        )
        dm_embed.add_field(
            name="Next Step",
            value="Staff will connect with your Roblox account (`" + order["roblox_username"] + "`) to conduct the in-game trade.",
            inline=False,
        )
        dm_ok = await send_customer_dm(interaction.client, order["customer_id"], dm_embed)
        if not dm_ok:
            await interaction.channel.send("⚠️ Customer DMs are closed. Please reach out to customer directly in a ticket or public mention.")

        await interaction.followup.send(f"✅ Order `{self.order_id}` accepted.", ephemeral=True)

    @discord.ui.button(label="Record Upfront Deposit", style=discord.ButtonStyle.primary, emoji="💰", row=0)
    async def record_deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RecordPaymentModal(order_id=self.order_id, stage="UPFRONT", parent_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Start Service", style=discord.ButtonStyle.primary, emoji="⚔️", row=0)
    async def start_service_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        order = await db.get_order(self.order_id)
        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            await db.update_order_status(
                order_id=self.order_id,
                new_status="IN_PROGRESS",
                actor_id=interaction.user.id,
                actor_tag=str(interaction.user),
                details="Staff marked service as in progress",
            )
        except ValueError as err:
            await interaction.followup.send(f"❌ Cannot start service: {err}", ephemeral=True)
            return

        await interaction.channel.send(f"⚔️ Order `{self.order_id}` is now **IN PROGRESS** (handled by {interaction.user.mention}).")

        # DM customer
        dm_embed = discord.Embed(
            title=f"⚔️ Service Started: `{self.order_id}`",
            description=f"Our staff has begun work on your service: **{order['service_name']}**!",
            color=discord.Color.blue(),
        )
        dm_ok = await send_customer_dm(interaction.client, order["customer_id"], dm_embed)
        if not dm_ok:
            await interaction.channel.send("⚠️ Customer DMs are closed.")

        await interaction.followup.send(f"✅ Marked `{self.order_id}` as in progress.", ephemeral=True)

    @discord.ui.button(label="Mark Completed", style=discord.ButtonStyle.green, emoji="🎉", row=1)
    async def mark_completed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        order = await db.get_order(self.order_id)
        if not order:
            await interaction.response.send_message("Order not found.", ephemeral=True)
            return

        await interaction.response.defer()

        # If one-time full payment, close order directly
        if order["payment_plan"] == PaymentPlan.FULL_UPFRONT.value:
            new_status = "PAID_AND_CLOSED"
            try:
                await db.update_order_status(
                    order_id=self.order_id,
                    new_status=new_status,
                    actor_id=interaction.user.id,
                    actor_tag=str(interaction.user),
                    details="Service completed and order closed (full upfront plan)",
                )
            except ValueError as err:
                await interaction.followup.send(f"❌ Cannot complete order: {err}", ephemeral=True)
                return

            await interaction.channel.send(f"🎉 Order `{self.order_id}` is **COMPLETED & CLOSED**! Thank you for your service.")

            dm_embed = discord.Embed(
                title=f"🎉 Service Completed & Closed: `{self.order_id}`",
                description=f"Your order for **{order['service_name']}** has been successfully completed! Thank you for choosing Blox Fruit Services.",
                color=discord.Color.gold(),
            )
        else:
            new_status = "COMPLETED_AWAITING_BALANCE"
            try:
                await db.update_order_status(
                    order_id=self.order_id,
                    new_status=new_status,
                    actor_id=interaction.user.id,
                    actor_tag=str(interaction.user),
                    details="Service completed; awaiting remaining 50% balance",
                )
            except ValueError as err:
                await interaction.followup.send(f"❌ Cannot complete order: {err}", ephemeral=True)
                return

            await interaction.channel.send(
                f"🎉 Service for `{self.order_id}` completed! Status is now **AWAITING REMAINING BALANCE** ({format_m(order['balance_remaining_m'])})."
            )

            dm_embed = discord.Embed(
                title=f"🎉 Service Finished: `{self.order_id}`",
                description=(
                    f"Your service **{order['service_name']}** is complete!\n"
                    f"Please arrange to trade the remaining 50% balance of **{format_m(order['balance_remaining_m'])}** with staff."
                ),
                color=discord.Color.gold(),
            )

        dm_ok = await send_customer_dm(interaction.client, order["customer_id"], dm_embed)
        if not dm_ok:
            await interaction.channel.send("⚠️ Customer DMs are closed.")

        await interaction.followup.send(f"✅ Updated completion status for `{self.order_id}`.", ephemeral=True)

    @discord.ui.button(label="Record Balance Payment", style=discord.ButtonStyle.primary, emoji="💳", row=1)
    async def record_balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RecordPaymentModal(order_id=self.order_id, stage="BALANCE", parent_view=self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Request Info", style=discord.ButtonStyle.secondary, emoji="❓", row=2)
    async def request_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RequestInfoModal(order_id=self.order_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel / Reject", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CancelOrderModal(order_id=self.order_id)
        await interaction.response.send_modal(modal)


class StaffControlsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffControlsCog(bot))
