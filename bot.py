"""
Blox Fruit Services - Discord Bot Main Entry Point.
Runs discord.py with slash command tree, persistent interactive views, and modular cogs.
Enforces fail-safe startup: halts if any required cog fails to load.
"""

import asyncio
import logging
import sys
import traceback
import discord
from discord.ext import commands

from config import Config
from core.database import db
from core.catalog import catalog
from cogs.ordering import PublicOrderPanelView


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("BloxFruitBot")

# Required cogs for essential bot operation
REQUIRED_COGS = [
    "cogs.ordering",
    "cogs.staff_controls",
    "cogs.admin_commands",
]


class BloxFruitBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        logger.info("Initializing database and catalog...")
        try:
            db.init_db()
            catalog.load()
        except Exception as e:
            logger.critical("Failed to initialize database or catalog: %s", e, exc_info=True)
            raise SystemExit(f"Fatal Startup Error: Could not initialize database or catalog: {e}")

        # Register persistent views so buttons continue working after bot restarts
        self.add_view(PublicOrderPanelView())
        logger.info("Registered persistent views.")

        # Load extension cogs - fail safely if any required cog fails
        failed_cogs = []
        for cog in REQUIRED_COGS:
            try:
                await self.load_extension(cog)
                logger.info("Loaded required cog: %s", cog)
            except Exception as e:
                logger.critical("FATAL: Failed to load required cog '%s': %s", cog, e)
                logger.error(traceback.format_exc())
                failed_cogs.append((cog, str(e)))

        if failed_cogs:
            error_details = "\n".join([f"• {c}: {err}" for c, err in failed_cogs])
            logger.critical("Startup aborted. The following required cogs failed to load:\n%s", error_details)
            await self.close()
            raise SystemExit(f"Startup aborted due to failed cogs: {failed_cogs}")

        # Sync slash commands
        if Config.GUILD_ID:
            guild = discord.Object(id=Config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d slash command(s) to guild %d", len(synced), Config.GUILD_ID)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d global slash command(s)", len(synced))

    async def on_ready(self):
        logger.info("========================================")
        logger.info("Blox Fruit Services Bot is ONLINE!")
        logger.info("Logged in as: %s (ID: %s)", self.user.name, self.user.id)
        logger.info("Active Catalog Version: %s", catalog.version)
        logger.info("Active Services: %d", sum(len(c.active_services()) for c in catalog.categories.values()))
        logger.info("========================================")

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Blox Fruit Services | /help",
        )
        await self.change_presence(status=discord.Status.online, activity=activity)


def main():
    errors = Config.validate()
    if errors:
        for err in errors:
            logger.error("Configuration Error: %s", err)
        logger.error("Please configure your .env file before starting the bot.")
        sys.exit(1)

    bot = BloxFruitBot()
    try:
        bot.run(Config.BOT_TOKEN, log_handler=None)
    except (SystemExit, KeyboardInterrupt):
        logger.info("Bot process exited.")
        sys.exit(1)
    except Exception as exc:
        logger.critical("Bot terminated unexpectedly: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
