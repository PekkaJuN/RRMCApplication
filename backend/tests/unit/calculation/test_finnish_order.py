"""Finnish name order (archiving spec P1, AC30)."""

from app.calculation.names import finnish_key


def test_ac30_scandinavian_letters_sort_after_z_in_finnish_order() -> None:
    names = ["Öljyt", "omenat", "Äyriäiset", "Banaanit"]

    assert sorted(names, key=finnish_key) == ["Banaanit", "omenat", "Äyriäiset", "Öljyt"]


def test_ac30_a_ring_comes_before_a_umlaut_before_o_umlaut() -> None:
    names = ["ö", "ä", "å", "z"]

    assert sorted(names, key=finnish_key) == ["z", "å", "ä", "ö"]


def test_ac30_case_does_not_decide_but_breaks_ties_stably() -> None:
    assert sorted(["b", "A", "a", "B"], key=finnish_key) == ["A", "a", "B", "b"]
