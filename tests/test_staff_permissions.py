"""
Tests for staff permission logic:
- Verifies server-side authorization check (is_staff)
- Verifies regular members without staff roles are rejected
- Verifies staff roles, admin roles, and administrator permissions are accepted
"""

from unittest.mock import MagicMock
from core.permissions import is_staff
from config import Config


def test_regular_member_without_roles_denied():
    member = MagicMock()
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False
    member.roles = []

    assert is_staff(member) is False


def test_member_with_staff_role_allowed():
    Config.STAFF_ROLE_ID = 999111
    member = MagicMock()
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False

    role_mock = MagicMock()
    role_mock.id = 999111
    member.roles = [role_mock]

    assert is_staff(member) is True


def test_member_with_admin_role_allowed():
    Config.ADMIN_ROLE_ID = 888222
    member = MagicMock()
    member.guild_permissions.administrator = False
    member.guild_permissions.manage_guild = False

    role_mock = MagicMock()
    role_mock.id = 888222
    member.roles = [role_mock]

    assert is_staff(member) is True


def test_guild_administrator_allowed_even_without_roles():
    member = MagicMock()
    member.guild_permissions.administrator = True
    member.guild_permissions.manage_guild = True
    member.roles = []

    assert is_staff(member) is True
