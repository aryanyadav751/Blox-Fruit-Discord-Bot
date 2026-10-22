"""
Blox Fruit Services - Catalog Manager.
Loads and manages services from data/catalog.json.
Guarantees that unconfirmed/draft services are hidden from public customer ordering.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from config import Config


@dataclass
class Service:
    id: str
    name: str
    price_m: float
    description: str
    prerequisites: str = ""
    status: str = "active"  # "active" or "draft"
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass
class Category:
    id: str
    name: str
    description: str
    services: List[Service] = field(default_factory=list)

    def active_services(self) -> List[Service]:
        return [s for s in self.services if s.is_active]


class CatalogManager:
    def __init__(self, catalog_path: Optional[Path] = None):
        self.catalog_path = catalog_path or Config.CATALOG_PATH
        self.version = "1.0.0"
        self.currency_label = "M estimated trade value"
        self.categories: Dict[str, Category] = {}
        self.services: Dict[str, Service] = {}
        self.load()

    def load(self) -> None:
        if not self.catalog_path.exists():
            raise FileNotFoundError(f"Catalog file not found at: {self.catalog_path}")

        with open(self.catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.version = data.get("version", "1.0.0")
        self.currency_label = data.get("currency_label", "M estimated trade value")
        self.categories.clear()
        self.services.clear()

        for cat_data in data.get("categories", []):
            cat_id = cat_data["id"]
            cat_services = []

            for s_data in cat_data.get("services", []):
                service = Service(
                    id=s_data["id"],
                    name=s_data["name"],
                    price_m=float(s_data["price_m"]),
                    description=s_data.get("description", ""),
                    prerequisites=s_data.get("prerequisites", ""),
                    status=s_data.get("status", "active"),
                    notes=s_data.get("notes", ""),
                )
                cat_services.append(service)
                self.services[service.id] = service

            category = Category(
                id=cat_id,
                name=cat_data["name"],
                description=cat_data.get("description", ""),
                services=cat_services,
            )
            self.categories[cat_id] = category

    def save(self) -> None:
        """Saves current catalog back to JSON file."""
        data = {
            "version": self.version,
            "currency_label": self.currency_label,
            "categories": [],
        }

        for cat in self.categories.values():
            cat_dict = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "services": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "price_m": s.price_m,
                        "description": s.description,
                        "prerequisites": s.prerequisites,
                        "status": s.status,
                        "notes": s.notes,
                    }
                    for s in cat.services
                ],
            }
            data["categories"].append(cat_dict)

        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_active_categories(self) -> List[Category]:
        """Returns categories that have at least one active service."""
        return [c for c in self.categories.values() if len(c.active_services()) > 0]

    def get_service(self, service_id: str) -> Optional[Service]:
        return self.services.get(service_id)

    def get_category_for_service(self, service_id: str) -> Optional[Category]:
        for cat in self.categories.values():
            for s in cat.services:
                if s.id == service_id:
                    return cat
        return None

    def update_price(self, service_id: str, new_price_m: float, activate: bool = False) -> bool:
        service = self.get_service(service_id)
        if not service:
            return False
        service.price_m = round(float(new_price_m), 2)
        if activate:
            service.status = "active"
        self.save()
        return True

    def set_service_status(self, service_id: str, status: str) -> bool:
        service = self.get_service(service_id)
        if not service:
            return False
        service.status = status
        self.save()
        return True


# Global singleton instance
catalog = CatalogManager()
