"""Variants: the ways of reading a receipt that a run compares (PC3)."""

from dataclasses import dataclass
from typing import Literal

from evaluation.truth import Receipt

type VariantKind = Literal["ocr", "vision"]

_KINDS = ("ocr", "vision")
# Ollama sends a request for these models to its cloud service.
_CLOUD_SUFFIXES = ("-cloud", ":cloud")


class VariantError(Exception):
    """A variant given on the command line cannot be used."""


@dataclass(frozen=True)
class Variant:
    kind: VariantKind
    model: str
    limit: int | None = None
    full_only: bool = False

    @property
    def text(self) -> str:
        return f"{self.kind}:{self.model}"

    @property
    def folder(self) -> str:
        """The detail folder name: colons are not allowed in Windows file names."""
        return self.text.replace(":", "-")


def parse_variant(text: str) -> Variant:
    """Read `ocr:<model>` or `vision:<model>`.

    Raises:
        VariantError: the text is malformed or names a cloud model.
    """
    kind, _, model = text.partition(":")
    if kind not in _KINDS or not model.strip():
        raise VariantError(f"Invalid variant: {text} (expected ocr:<model> or vision:<model>)")
    if model.lower().endswith(_CLOUD_SUFFIXES):
        raise VariantError(f"Cloud models are not allowed: {text}")
    return Variant(kind=kind, model=model)


def select_receipts(receipts: list[Receipt], variant: Variant) -> list[Receipt]:
    """The receipts a variant reads: the full subset if asked, then the first `limit`."""
    selected = [r for r in receipts if r.truth.is_full] if variant.full_only else receipts
    return selected[: variant.limit] if variant.limit is not None else selected
