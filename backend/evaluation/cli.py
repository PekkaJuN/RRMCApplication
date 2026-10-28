"""Command line: `python -m evaluation init|run` (PC1, PC3, PC6, PC8).

Exit codes: 0 done, 1 Ollama cannot be used, 2 invalid input, 3 unexpected error.
"""

import argparse
import datetime
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.settings import Settings, SettingsError, load_settings
from evaluation.ocr import Ocr, TesseractOcr
from evaluation.ollama import OllamaReader, Reader
from evaluation.report import render_summary
from evaluation.runner import run_evaluation
from evaluation.truth import TruthFileError, collect_receipts, init_templates
from evaluation.variants import Variant, VariantError, parse_variant

# The `eval` service mounts RRMC_EVAL_DIR here.
DEFAULT_DIR = Path("/data/eval")
EXIT_OLLAMA = 1
EXIT_INPUT = 2
EXIT_UNEXPECTED = 3


@dataclass(frozen=True)
class Deps:
    ocr: Ocr
    reader: Reader
    clock: Callable[[], float]
    now: Callable[[], datetime.datetime]


def default_deps(settings: Settings) -> Deps:
    # The only address the tool ever calls (AC19).
    return Deps(
        ocr=TesseractOcr(),
        reader=OllamaReader(str(settings.ollama_url)),
        clock=time.monotonic,
        now=datetime.datetime.now,
    )


@dataclass(frozen=True)
class _VariantOption:
    text: str
    limit: int | None = None
    full_only: bool = False


class _VariantAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        _: Any = None,
    ) -> None:
        options: list[_VariantOption] = getattr(namespace, self.dest) or []
        setattr(namespace, self.dest, [*options, _VariantOption(str(values))])


class _SelectionAction(argparse.Action):
    """`--limit` and `--subset` change the variant given just before them."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        _: Any = None,
    ) -> None:
        options: list[_VariantOption] = getattr(namespace, "variants", None) or []
        if not options:
            parser.error(f"{self.option_strings[0]} must follow a --variant")
        if self.dest == "limit":
            last = replace(options[-1], limit=int(values))
        else:
            last = replace(options[-1], full_only=True)
        namespace.variants = [*options[:-1], last]


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number") from None
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m evaluation")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="create truth file templates for new images")
    run = commands.add_parser("run", help="compare reading variants")
    for command in (init, run):
        command.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="evaluation folder")
    run.add_argument(
        "--variant",
        dest="variants",
        action=_VariantAction,
        required=True,
        help="ocr:<model> or vision:<model>; repeat to compare",
    )
    run.add_argument(
        "--limit", type=_positive, action=_SelectionAction, help="first N receipts only"
    )
    run.add_argument(
        "--subset", choices=["full"], action=_SelectionAction, help="receipts with lines only"
    )
    return parser


def main(argv: Sequence[str], deps: Deps | None = None) -> int:
    args = _parser().parse_args(argv)
    folder: Path = args.dir
    if not folder.is_dir():
        return _fail(f"Evaluation folder not found: {folder}", EXIT_INPUT)
    if args.command == "init":
        print(f"Created {init_templates(folder)} template(s).")
        return 0

    try:
        variants = _variants(args.variants)
        collected = collect_receipts(folder)
        deps = deps or default_deps(load_settings())
    except (VariantError, TruthFileError, SettingsError) as error:
        return _fail(str(error), EXIT_INPUT)
    problems = deps.reader.check([variant.model for variant in variants])
    if problems:
        return _fail("\n".join(problems), EXIT_OLLAMA)

    run_id = deps.now().strftime("%Y%m%d-%H%M%S")
    results_dir = folder / "results" / run_id
    try:
        rows = run_evaluation(
            results_dir=results_dir,
            receipts=collected.receipts,
            variants=variants,
            ocr=deps.ocr,
            reader=deps.reader,
            clock=deps.clock,
            out=lambda line: print(line, flush=True),
        )
        summary = render_summary(run_id, rows, collected.skipped)
        (results_dir / "summary.md").write_text(summary, encoding="utf-8")
    except Exception as error:
        # A message or traceback may hold a file name or receipt text (AC18, AC21).
        return _fail(f"Evaluation failed: {type(error).__name__}", EXIT_UNEXPECTED)
    print(summary, end="")
    return 0


def _variants(options: Sequence[_VariantOption]) -> list[Variant]:
    """Parse every variant; two may not share a detail folder.

    Raises:
        VariantError: a variant is invalid, a cloud model or a repeat.
    """
    variants: list[Variant] = []
    for option in options:
        variant = parse_variant(option.text)
        if any(v.folder == variant.folder for v in variants):
            raise VariantError(f"Duplicate variant: {option.text}")
        variants.append(replace(variant, limit=option.limit, full_only=option.full_only))
    return variants


def _fail(message: str, code: int) -> int:
    print(message, file=sys.stderr)
    return code
