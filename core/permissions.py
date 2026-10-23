"""
Blox Fruit Services - Role & Permission Verification Engine.
Handles server-side authorization checks for staff and administrator roles.
"""

from typing import Any
from config import Config


def is_staff(member: Any) -> bool:
    """
    Server-side authorization check.
    Verifies caller has Administrator permissions, Manage Guild permissions,
    or holds the configured STAFF_ROLE_ID or ADMIN_ROLE_ID.
    """
    if not member or not hasattr(member, "guild_permissions"):
        return False

    perms = member.guild_permissions
    if getattr(perms, "administrator", False) or getattr(perms, "manage_guild", False):
        return True

    staff_role_id = Config.STAFF_ROLE_ID
    admin_role_id = Config.ADMIN_ROLE_ID
    user_role_ids = [getattr(r, "id", None) for r in getattr(member, "roles", [])]

    return bool(
        (staff_role_id and staff_role_id in user_role_ids)
        or (admin_role_id and admin_role_id in user_role_ids)
    )
