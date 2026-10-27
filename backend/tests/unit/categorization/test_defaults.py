import sqlite3
from datetime import UTC, datetime

from app.categorization.defaults import DEFAULT_CATEGORIES, seed_defaults
from app.storage.catalog_repository import CatalogRepository

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)

RUOKA = [
    "Maitotuotteet",
    "Liha",
    "Kala",
    "Hedelmät",
    "Vihannekset",
    "Kananmunat",
    "Lihan korvaajat",
    "Leivät",
    "Kuivatuotteet",
    "Pakasteet",
]
AUTO = ["Polttoaineet", "Autotarvikkeet", "Autohuolto"]
UNGROUPED = [
    "Juomat",
    "Alkoholi",
    "Herkut",
    "Hygienia",
    "Kodin tarvikkeet",
    "Lemmikit",
    "Ulkona syöminen",
    "Muut",
]


def test_ac1_default_list_matches_prd_6_9() -> None:
    expected = (("Ruoka", tuple(RUOKA)), ("Auto", tuple(AUTO)), (None, tuple(UNGROUPED)))

    assert expected == DEFAULT_CATEGORIES


def test_ac1_seeding_an_empty_database_creates_the_default_list(db: sqlite3.Connection) -> None:
    repo = CatalogRepository(db)

    seed_defaults(repo, NOW)

    rows = repo.list_categories()
    groups = {row.id: row.name for row in rows if row.kind == "group"}
    children = {
        name: sorted(row.name for row in rows if row.parent_id == group_id)
        for group_id, name in groups.items()
    }
    ungrouped = sorted(row.name for row in rows if row.kind == "category" and row.parent_id is None)
    assert children == {"Ruoka": sorted(RUOKA), "Auto": sorted(AUTO)}
    assert ungrouped == sorted(UNGROUPED)
    assert len(rows) == 23
    assert repo.get_app_state("catalog_seeded_at") == NOW.isoformat()


def test_ac1_default_names_are_stored_with_their_normalized_key(db: sqlite3.Connection) -> None:
    repo = CatalogRepository(db)

    seed_defaults(repo, NOW)

    row = repo.get_category_by_key("ulkona syöminen")
    assert row is not None
    assert row.name == "Ulkona syöminen"


def test_ac2_seeding_again_after_everything_was_deleted_creates_nothing(
    db: sqlite3.Connection,
) -> None:
    repo = CatalogRepository(db)
    seed_defaults(repo, NOW)
    for row in sorted(repo.list_categories(), key=lambda row: row.kind != "category"):
        repo.delete_category(row.id)

    seed_defaults(repo, NOW)

    assert repo.list_categories() == []
