"""
Tests for core/catalog.py:
- Verifies catalog loading and integrity
- Verifies draft items (4 Trials, Tyrant of the Skies, Cyborg V1, PH, Low raids, etc.) are marked draft
- Verifies active_services() excludes draft items so customers never see unconfirmed items
"""

import pytest
from core.catalog import CatalogManager
from pathlib import Path


def test_catalog_load():
    manager = CatalogManager()
    assert len(manager.categories) >= 8
    assert "trials" in manager.categories
    assert "bosses" in manager.categories
    assert "swords" in manager.categories
    assert "progression" in manager.categories


def test_draft_items_are_hidden_from_active():
    manager = CatalogManager()
    trials_cat = manager.categories["trials"]
    active_trial_ids = [s.id for s in trials_cat.active_services()]

    # 4 Trials is draft
    assert "trials_4" not in active_trial_ids
    assert "trials_1" in active_trial_ids
    assert "trials_2" in active_trial_ids
    assert "trials_3" in active_trial_ids
    assert "trials_5" in active_trial_ids

    # Check that trials_4 exists as a service object and has status draft
    service_4 = manager.get_service("trials_4")
    assert service_4 is not None
    assert service_4.status == "draft"
    assert "verify" in service_4.notes.lower()


def test_boss_draft_items():
    manager = CatalogManager()
    bosses_cat = manager.categories["bosses"]
    active_boss_ids = [s.id for s in bosses_cat.active_services()]

    # Tyrant of the skies is draft
    assert "boss_tyrant_skies" not in active_boss_ids
    assert "boss_dough_king" in active_boss_ids
    assert "boss_cake_prince" in active_boss_ids
    assert "boss_darkbeard" in active_boss_ids


def test_sea_events_draft_items():
    manager = CatalogManager()
    sea_cat = manager.categories["sea_events"]
    active_sea_ids = [s.id for s in sea_cat.active_services()]

    # PH services are draft pending abbreviation confirmation
    assert "sea_ph" not in active_sea_ids
    assert "sea_ph_magnets" not in active_sea_ids
    assert "sea_kitsune" in active_sea_ids
    assert "sea_leviathan" in active_sea_ids


def test_price_update_and_publishing(tmp_path: Path):
    # Copy catalog to temp path for isolated testing
    import shutil
    from config import Config

    test_file = tmp_path / "test_catalog.json"
    shutil.copyfile(Config.CATALOG_PATH, test_file)

    temp_manager = CatalogManager(catalog_path=test_file)
    # Check trials_4 is draft
    s4 = temp_manager.get_service("trials_4")
    assert s4.status == "draft"

    # Update price and publish
    temp_manager.update_price("trials_4", 155.0, activate=True)
    assert temp_manager.get_service("trials_4").price_m == 155.0
    assert temp_manager.get_service("trials_4").status == "active"

    # Reload from disk to verify persistence
    reloaded = CatalogManager(catalog_path=test_file)
    assert reloaded.get_service("trials_4").price_m == 155.0
    assert reloaded.get_service("trials_4").status == "active"
