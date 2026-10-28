"""Truth files: the values the user reads from each paper receipt (PC1, PC2)."""

import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import ErrorDetails

TRUTH_SUFFIX = ".truth.json"
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
TEMPLATE: dict[str, Any] = {
    "store": "",
    "date": "YYYY-MM-DD",
    "total_cents": 0,
    "line_count": 0,
    "lines": [],
}

# Messages name the field only: the value may be receipt content.
_PROBLEMS = {
    "missing": "is required",
    "int_type": "must be an integer",
    "int_parsing": "must be an integer",
    "int_from_float": "must be an integer",
    "date_type": "must be a date YYYY-MM-DD",
    "date_parsing": "must be a date YYYY-MM-DD",
    "date_from_datetime_parsing": "must be a date YYYY-MM-DD",
    "date_from_datetime_inexact": "must be a date YYYY-MM-DD",
    "string_too_short": "must not be empty",
    "string_type": "must be text",
    "list_type": "must be a list",
    "greater_than_equal": "must not be negative",
    "extra_forbidden": "is not a known field",
    "model_type": "must be a JSON object",
}


class TruthFileError(Exception):
    """A truth file cannot be used. The message never contains a value from the file."""

    def __init__(self, file_name: str, problem: str) -> None:
        super().__init__(f"Invalid truth file {file_name}: {problem}")


class TruthLine(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    amount_cents: int


class Truth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    store: str = Field(min_length=1)
    date: datetime.date
    total_cents: int
    line_count: int = Field(ge=0)
    lines: list[TruthLine] | None = None

    @property
    def is_full(self) -> bool:
        """The receipt belongs to the full subset: its lines were written down."""
        return bool(self.lines)


@dataclass(frozen=True)
class Receipt:
    index: int
    image: Path
    truth: Truth


@dataclass(frozen=True)
class Collected:
    receipts: list[Receipt]
    skipped: int


def truth_path(image: Path) -> Path:
    return image.with_name(image.name + TRUTH_SUFFIX)


def list_images(folder: Path) -> list[Path]:
    """JPEG and PNG files directly in the folder, in name order ignoring case."""
    images = [
        path
        for path in folder.iterdir()
        if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file() and not path.is_symlink()
    ]
    return sorted(images, key=lambda path: path.name.casefold())


def init_templates(folder: Path) -> int:
    """Create a template truth file for every image without one; return how many."""
    created = 0
    for image in list_images(folder):
        try:
            # "x" never overwrites a truth file the user has written.
            with truth_path(image).open("x", encoding="utf-8") as file:
                file.write(json.dumps(TEMPLATE, indent=2) + "\n")
        except FileExistsError:
            continue
        created += 1
    return created


def load_truth(path: Path) -> Truth | None:
    """Read a truth file; None when it is still the unchanged template.

    Raises:
        TruthFileError: the file cannot be read or does not match the format.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise TruthFileError(path.name, "cannot be read") from None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raise TruthFileError(path.name, "not valid JSON") from None
    if raw == TEMPLATE:
        return None
    try:
        # Strict JSON mode still reads ISO date strings, but refuses "12,50" or 12.5 for cents.
        return Truth.model_validate_json(text, strict=True)
    except ValidationError as error:
        raise TruthFileError(path.name, _describe(error.errors()[0])) from None


def collect_receipts(folder: Path) -> Collected:
    """Receipts with a filled truth file, numbered in name order; count the others.

    Raises:
        TruthFileError: a truth file is invalid.
    """
    receipts: list[Receipt] = []
    skipped = 0
    for image in list_images(folder):
        path = truth_path(image)
        truth = load_truth(path) if path.is_file() else None
        if truth is None:
            skipped += 1
            continue
        receipts.append(Receipt(index=len(receipts) + 1, image=image, truth=truth))
    return Collected(receipts=receipts, skipped=skipped)


def _describe(error: ErrorDetails) -> str:
    problem = _PROBLEMS.get(error["type"], "is invalid")
    field = _field_name(error["loc"])
    return f"{field} {problem}" if field else problem


def _field_name(location: tuple[int | str, ...]) -> str:
    name = ""
    for part in location:
        name += f"[{part}]" if isinstance(part, int) else (f".{part}" if name else part)
    return name
