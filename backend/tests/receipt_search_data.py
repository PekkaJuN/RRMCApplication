"""The synthetic receipts R1–R5 of the receipt search spec (AC1–AC7)."""

import sqlite3

from app.categorization.names import normalize_key
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-10-28T10:00:00Z"


def _category(catalog: CatalogRepository, name: str) -> int:
    existing = catalog.get_category_by_key(normalize_key(name))
    if existing is not None:
        return existing.id
    return catalog.add_category(name, normalize_key(name), "category", None)


def seed_search_receipts(db: sqlite3.Connection) -> dict[str, int]:
    """Store R1–R5 and return their ids by name. R1–R4 are reviewed, R5 is not."""
    catalog = CatalogRepository(db)
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        milk = _category(catalog, "Hakutesti maito")
        bread = _category(catalog, "Hakutesti leipä")
        fish = _category(catalog, "Hakutesti kala")
        light_milk = catalog.add_product("Kevytmaito 1L", "kevytmaito 1l", milk)
        oat_drink = catalog.add_product("Kaurajuoma", "kaurajuoma", milk)

        def receipt(number: int, purchase_date: str | None) -> int:
            return receipts.add(
                f"{number + 900:064d}", f"haku{number}.jpg", TIME, purchase_date=purchase_date
            ).id

        r1 = receipt(1, "2026-10-05")
        receipts.add_line(
            r1,
            1,
            "Kevytmaito 1L",
            125,
            is_deposit_refund=False,
            category=LineCategory(milk, "remembered", light_milk),
        )
        receipts.add_line(
            r1,
            2,
            "Leipä",
            300,
            is_deposit_refund=False,
            category=LineCategory(bread, "model", None),
        )
        r2 = receipt(2, "2026-10-04")
        receipts.add_line(
            r2,
            1,
            "KAURAJUOMA",
            199,
            is_deposit_refund=False,
            category=LineCategory(milk, "user", oat_drink),
        )
        receipts.add_line(r2, 2, "PORKKANA", 89, is_deposit_refund=False)
        r3 = receipt(3, "2026-10-03")
        receipts.add_line(r3, 1, "Panttipalautus", -40, is_deposit_refund=True)
        r4 = receipt(4, "2026-10-02")
        receipts.add_line(r4, 1, "MAITOSUKLAA", 250, is_deposit_refund=False)
        r5 = receipt(5, None)
        receipts.add_line(
            r5,
            1,
            "Äyriäiset",
            899,
            is_deposit_refund=False,
            category=LineCategory(fish, "model", None),
        )
        for reviewed in (r1, r2, r3, r4):
            receipts.set_reviewed(reviewed, reviewed=True)
    return {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5}
