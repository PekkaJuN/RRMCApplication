"""The prompt, the answer schema and answer parsing, shared by every variant (PC4)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

# Short keys keep the answer small: output tokens are the slowest part on the CPU.
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "s": {"type": "string"},
        "d": {"type": "string"},
        "t": {"type": "integer"},
        "l": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "string"},
                    "a": {"type": "integer"},
                    "r": {"type": "boolean"},
                },
                "required": ["n", "a", "r"],
            },
        },
    },
    "required": ["s", "d", "t", "l"],
}

# The Finnish receipt rules of PRD FR-9.
INSTRUCTIONS = """\
You read one Finnish shop receipt and answer with JSON only.

Fields:
- "s": the store name as printed at the top.
- "d": the purchase date as YYYY-MM-DD.
- "t": the receipt total (YHTEENSÄ) in integer cents.
- "l": the purchased lines in printed order. Each line has "n" (the product name as \
printed), "a" (the line amount in integer cents) and "r" (true only for a deposit refund).

Rules:
- Amounts use a decimal comma: 1,25 is 125 cents. Never answer a decimal number.
- A weighed item may be printed over two lines (weight and unit price, then the amount): \
it is one line.
- A discount line printed under an item is merged into that item: the item's amount is the \
net price after the discount. Do not add the discount as its own line.
- A deposit line (pantti) printed under an item is merged into that item: the item's \
amount includes the deposit, e.g. 1,89 + 0,40 = 229. Do not add the deposit as its own line.
- A deposit refund (panttipalautus) is its own line with a negative amount and "r": true.
- Ignore bonus lines, the VAT summary (ALV), and the card payment slip after the total.
"""


class AnswerLine(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    n: str
    a: int
    r: bool


class Answer(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    s: str
    d: str
    t: int
    l: list[AnswerLine]  # noqa: E741 - the compact key of the answer schema


def text_prompt(ocr_text: str) -> str:
    return f"{INSTRUCTIONS}\nReceipt text:\n{ocr_text}\n"


def image_prompt() -> str:
    return f"{INSTRUCTIONS}\nThe receipt is in the attached image.\n"


def parse_answer(raw: str) -> Answer | None:
    """The model's answer, or None when it is not JSON matching the schema."""
    try:
        return Answer.model_validate_json(raw, strict=True)
    except ValidationError:
        return None
