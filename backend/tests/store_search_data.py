"""The synthetic receipts S1–S6 of the store search spec (AC1–AC8)."""

import sqlite3

from app.categorization.names import normalize_key
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-11-23T10:00:00Z"


def _category(catalog: CatalogRepository, name: str) -> int:
    existing = catalog.get_category_by_key(normalize_key(name))
    if existing is not None:
        return existing.id
    return catalog.add_category(name, normalize_key(name), "category", None)


def seed_store_receipts(db: sqlite3.Connection) -> dict[str, int]:
    """Store S1–S6 and return their ids by name."""
    catalog = CatalogRepository(db)
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        category = LineCategory(_category(catalog, "Kauppatesti"), "model", None)

        def receipt(number: int, store: str | None, purchase_date: str | None) -> int:
            return receipts.add(
                f"{number + 800:064d}",
                f"kauppa{number}.jpg",
                TIME,
                store=store,
                purchase_date=purchase_date,
            ).id

        s1 = receipt(1, "K-Market Keskusta", "2026-10-05")
        receipts.add_line(s1, 1, "Maito", 125, is_deposit_refund=False, category=category)
        s2 = receipt(2, "Prisma Itäkeskus", "2026-10-04")
        receipts.add_line(s2, 1, "PORKKANA", 89, is_deposit_refund=False)
        s3 = receipt(3, "K-Citymarket", "2026-10-03")
        receipts.add_line(s3, 1, "MAITOSUKLAA", 250, is_deposit_refund=False)
        s4 = receipt(4, "", "2026-10-02")
        receipts.add_line(s4, 1, "Leipä", 300, is_deposit_refund=False, category=category)
        s5 = receipt(5, None, None)
        s6 = receipt(6, "ÄRRÄ Asema", "2026-10-01")
        receipts.add_line(s6, 1, "Kahvi", 450, is_deposit_refund=False, category=category)
    return {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6}
