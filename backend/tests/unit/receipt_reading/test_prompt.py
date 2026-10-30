import pytest

from app.receipt_reading.prompt import Answer, AnswerLine, parse_answer, text_prompt

VALID = (
    '{"s": "Testikauppa", "d": "2026-10-05", "t": 125, "l": [{"n": "Maito", "a": 125, "r": false}]}'
)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"s": "x", "d": "2026-10-05", "t": 3.49, "l": []}',
        '{"s": "x", "d": "2026-10-05", "t": 349}',
        '{"s": "x", "d": "2026-10-05", "t": 125, "l": [{"n": "Maito", "a": "125", "r": false}]}',
    ],
)
def test_ac8_answers_not_matching_the_schema_are_none(raw: str) -> None:
    assert parse_answer(raw) is None


def test_schema_valid_answer_is_parsed() -> None:
    assert parse_answer(VALID) == Answer(
        s="Testikauppa", d="2026-10-05", t=125, l=[AnswerLine(n="Maito", a=125, r=False)]
    )


def test_ac7_text_prompt_holds_the_ocr_text_and_the_fi_rules() -> None:
    prompt = text_prompt("MAITO 1,25")

    assert "MAITO 1,25" in prompt
    assert "pantti" in prompt
    assert "decimal comma" in prompt
