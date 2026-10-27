"""The default category list of PRD section 6.9, created once on first start (PC2)."""

from datetime import datetime

from app.categorization.names import normalize_key
from app.storage.catalog_repository import CatalogRepository

SEEDED_KEY = "catalog_seeded_at"

# (group, its categories); None holds the categories without a group.
DEFAULT_CATEGORIES: tuple[tuple[str | None, tuple[str, ...]], ...] = (
    (
        "Ruoka",
        (
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
        ),
    ),
    ("Auto", ("Polttoaineet", "Autotarvikkeet", "Autohuolto")),
    (
        None,
        (
            "Juomat",
            "Alkoholi",
            "Herkut",
            "Hygienia",
            "Kodin tarvikkeet",
            "Lemmikit",
            "Ulkona syöminen",
            "Muut",
        ),
    ),
)


def seed_defaults(repository: CatalogRepository, now: datetime) -> None:
    """Create the default list unless it was created before.

    A marker, not an empty table, decides: after the user deletes everything, the defaults
    must not come back (AC2).
    """
    with repository.transaction():
        if repository.get_app_state(SEEDED_KEY) is not None:
            return
        for group, categories in DEFAULT_CATEGORIES:
            group_id = None
            if group is not None:
                group_id = repository.add_category(group, normalize_key(group), "group", None)
            for name in categories:
                repository.add_category(name, normalize_key(name), "category", group_id)
        repository.set_app_state(SEEDED_KEY, now.isoformat())
