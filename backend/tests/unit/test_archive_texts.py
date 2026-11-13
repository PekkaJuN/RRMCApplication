"""The period warning sentence and the unreviewed message (archiving spec PC10, AC7, AC22, AC23)."""

from app import texts


def test_ac22_one_archived_year() -> None:
    assert texts.archived_years_note([2025]) == "Arkistoitu vuosi 2025 ei ole mukana."


def test_ac23_several_archived_years() -> None:
    assert (
        texts.archived_years_note([2024, 2025]) == "Arkistoidut vuodet 2024, 2025 eivät ole mukana."
    )


def test_ac7_unreviewed_message_uses_the_apps_wording() -> None:
    # "tarkistamaton", as the receipt list and the totals say it.
    assert texts.unreviewed_block_archiving(1) == (
        "Vuotta ei voi arkistoida: vuodella on 1 tarkistamaton kuitti."
    )
    assert texts.unreviewed_block_archiving(2) == (
        "Vuotta ei voi arkistoida: vuodella on 2 tarkistamatonta kuittia."
    )
