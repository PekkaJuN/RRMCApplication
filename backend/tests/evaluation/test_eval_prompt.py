import json

import pytest

from evaluation.prompt import (
    ANSWER_SCHEMA,
    INSTRUCTIONS,
    image_prompt,
    parse_answer,
    text_prompt,
)

ANSWER = {"s": "Kauppa", "d": "2026-01-02", "t": 125, "l": [{"n": "MAITO", "a": 125, "r": False}]}


def test_ac5_text_prompt_has_the_instructions_and_the_ocr_text() -> None:
    prompt = text_prompt("MAITO 1,25\nYHTEENSÄ 1,25")

    assert prompt.startswith(INSTRUCTIONS)
    assert "MAITO 1,25\nYHTEENSÄ 1,25" in prompt


def test_ac6_image_prompt_has_the_same_instructions() -> None:
    assert image_prompt().startswith(INSTRUCTIONS)


@pytest.mark.parametrize(
    "rule", ["decimal comma", "pantti", "panttipalautus", "discount", "card payment"]
)
def test_ac5_instructions_state_the_finnish_receipt_rules(rule: str) -> None:
    assert rule in INSTRUCTIONS.lower()


def test_ac5_schema_asks_for_the_compact_answer() -> None:
    assert ANSWER_SCHEMA["required"] == ["s", "d", "t", "l"]
    properties = ANSWER_SCHEMA["properties"]
    assert properties["t"] == {"type": "integer"}
    assert properties["l"]["items"]["required"] == ["n", "a", "r"]
    assert properties["l"]["items"]["properties"]["a"] == {"type": "integer"}
    assert properties["l"]["items"]["properties"]["r"] == {"type": "boolean"}


def test_ac5_valid_answer_is_parsed() -> None:
    answer = parse_answer(json.dumps(ANSWER))

    assert answer is not None
    assert (answer.s, answer.d, answer.t) == ("Kauppa", "2026-01-02", 125)
    assert [(line.n, line.a, line.r) for line in answer.l] == [("MAITO", 125, False)]


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps({k: v for k, v in ANSWER.items() if k != "t"}),
        json.dumps({**ANSWER, "t": 1.25}),
        json.dumps({**ANSWER, "t": "125"}),
        json.dumps({**ANSWER, "l": [{"n": "MAITO", "a": 125}]}),
        json.dumps([ANSWER]),
        "",
    ],
)
def test_ac11_invalid_answer_gives_none(raw: str) -> None:
    assert parse_answer(raw) is None
