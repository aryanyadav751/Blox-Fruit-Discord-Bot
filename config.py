"""
Blox Fruit Services - Configuration Loader.
Reads settings from environment variables and provides centralized access.
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        load_dotenv()
except ImportError:
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v


class Config:
    # Discord Bot Token
    BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "").strip()

    # Discord Guild (Server) ID
    GUILD_ID: int = int(os.getenv("GUILD_ID", "0"))

    # Configured channels
    ORDER_CHANNEL_ID: int = int(os.getenv("ORDER_CHANNEL_ID", "0"))
    STAFF_CHANNEL_ID: int = int(os.getenv("STAFF_CHANNEL_ID", "0"))

    # Configured staff & admin roles
    STAFF_ROLE_ID: int = int(os.getenv("STAFF_ROLE_ID", "0"))
    ADMIN_ROLE_ID: int = int(os.getenv("ADMIN_ROLE_ID", "0"))

    # File storage paths
    _raw_db = os.getenv("DATABASE_PATH", "data/blox_fruits.db")
    DATABASE_PATH: Path = BASE_DIR / _raw_db if not Path(_raw_db).is_absolute() else Path(_raw_db)

    _raw_cat = os.getenv("CATALOG_PATH", "data/catalog.json")
    if (BASE_DIR / _raw_cat).exists():
        CATALOG_PATH: Path = BASE_DIR / _raw_cat
    elif (BASE_DIR / "data" / Path(_raw_cat).name).exists():
        CATALOG_PATH: Path = BASE_DIR / "data" / Path(_raw_cat).name
    elif (BASE_DIR / "data/catalog.json").exists():
        CATALOG_PATH: Path = BASE_DIR / "data/catalog.json"
    else:
        CATALOG_PATH: Path = BASE_DIR / "catalog.json"

    @classmethod
    def validate(cls) -> list[str]:
        """Returns a list of missing critical configuration items."""
        missing = []
        if not cls.BOT_TOKEN or cls.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            missing.append("DISCORD_BOT_TOKEN is not configured in .env")
        return missing
