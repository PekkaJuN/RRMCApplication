import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.settings import Settings
from evaluation.cli import Deps, default_deps, main
from evaluation.ocr import TesseractOcr
from evaluation.ollama import OllamaReader, ReadResult
from evaluation.truth import TEMPLATE
from tests.evaluation.eval_fakes import (
    RIGHT_ANSWER,
    FakeClock,
    FakeOcr,
    FakeReader,
    image_bytes,
)

RUN_ID = "20260102-030405"
VALID = {"store": "Kauppa", "date": "2026-01-02", "total_cents": 125, "line_count": 1}


def deps(reader: FakeReader | None = None, ocr: FakeOcr | None = None) -> Deps:
    return Deps(
        ocr=ocr or FakeOcr(),
        reader=reader or FakeReader(),
        clock=FakeClock(),
        now=lambda: datetime.datetime(2026, 1, 2, 3, 4, 5),
    )


def add_receipt(folder: Path, name: str, truth: object | None = VALID) -> None:
    (folder / name).write_bytes(image_bytes())
    if truth is not None:
        (folder / f"{name}.truth.json").write_text(json.dumps(truth), encoding="utf-8")


def output(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


# --- init -------------------------------------------------------------------------------


def test_ac1_init_reports_the_created_templates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.jpg").write_bytes(b"image")

    code = main(["init", "--dir", str(tmp_path)], deps())

    assert code == 0
    assert output(capsys).strip() == "Created 1 template(s)."
    assert json.loads((tmp_path / "a.jpg.truth.json").read_text(encoding="utf-8")) == TEMPLATE


def test_missing_folder_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["init", "--dir", str(tmp_path / "none")], deps())

    assert code == 2
    assert "Evaluation folder not found" in output(capsys)


# --- run: input errors ------------------------------------------------------------------


def test_ac2_invalid_truth_file_stops_before_any_model_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_receipt(tmp_path, "a.jpg", {**VALID, "total_cents": "12,50"})
    add_receipt(tmp_path, "b.jpg")
    reader = FakeReader()

    code = main(["run", "--dir", str(tmp_path), "--variant", "ocr:m"], deps(reader))

    assert code == 2
    assert output(capsys).strip() == (
        "Invalid truth file a.jpg.truth.json: total_cents must be an integer"
    )
    assert reader.events == []


@pytest.mark.parametrize("variant", ["ocr:gpt-oss:120b-cloud", "vision:x:cloud"])
def test_ac8_cloud_model_is_refused_without_calling_ollama(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], variant: str
) -> None:
    reader = FakeReader()

    code = main(
        ["run", "--dir", str(tmp_path), "--variant", "ocr:m", "--variant", variant], deps(reader)
    )

    assert code == 2
    assert output(capsys).strip() == f"Cloud models are not allowed: {variant}"
    assert reader.events == []


@pytest.mark.parametrize("variant", ["qwen2.5:7b", "audio:x"])
def test_ac9_malformed_variant_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], variant: str
) -> None:
    code = main(["run", "--dir", str(tmp_path), "--variant", variant], deps())

    assert code == 2
    assert output(capsys).strip() == (
        f"Invalid variant: {variant} (expected ocr:<model> or vision:<model>)"
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["run"],
        ["run", "--limit", "2", "--variant", "ocr:m"],
        ["run", "--variant", "ocr:m", "--limit", "0"],
        ["run", "--variant", "ocr:m", "--subset", "half"],
        [],
    ],
)
def test_ac7_misused_options_exit_with_code_2(tmp_path: Path, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main([*argv, "--dir", str(tmp_path)] if argv else argv, deps())

    assert caught.value.code == 2


@pytest.mark.parametrize(
    "problem",
    [
        "Ollama is not reachable at http://host.docker.internal:11434",
        "Model m is not pulled. Run: ollama pull m",
    ],
)
def test_ac10_model_problem_stops_before_the_first_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], problem: str
) -> None:
    add_receipt(tmp_path, "a.jpg")
    reader = FakeReader(problems=[problem])

    code = main(["run", "--dir", str(tmp_path), "--variant", "ocr:m"], deps(reader))

    assert code == 1
    assert output(capsys).strip() == problem
    assert reader.events == ["check"]
    assert not (tmp_path / "results").exists()


def test_ac10_every_variant_model_is_checked(tmp_path: Path) -> None:
    reader = FakeReader()

    main(
        ["run", "--dir", str(tmp_path), "--variant", "ocr:m", "--variant", "vision:v"],
        deps(reader),
    )

    assert reader.checked == ["m", "v"]


# --- run: results -----------------------------------------------------------------------


def test_ac3_ac7_run_writes_details_and_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ["a.jpg", "b.jpg", "c.jpg"]:
        add_receipt(tmp_path, name)
    add_receipt(tmp_path, "d.jpg", truth=None)
    reader = FakeReader()

    code = main(
        [
            "run",
            "--dir",
            str(tmp_path),
            "--variant",
            "ocr:m",
            "--limit",
            "2",
            "--variant",
            "vision:v",
        ],
        deps(reader),
    )

    assert code == 0
    results = tmp_path / "results" / RUN_ID
    assert sorted(p.name for p in (results / "ocr-m").iterdir()) == ["1.json", "2.json"]
    assert sorted(p.name for p in (results / "vision-v").iterdir()) == [
        "1.json",
        "2.json",
        "3.json",
    ]
    summary = (results / "summary.md").read_text(encoding="utf-8")
    assert "Skipped without truth file: 1" in summary
    assert "| ocr:m | 2 |" in summary
    assert "| vision:v | 3 |" in summary
    printed = output(capsys)
    assert "ocr:m 1/2 5 s" in printed
    assert summary in printed


def test_ac7_subset_full_on_the_command_line(tmp_path: Path) -> None:
    add_receipt(tmp_path, "a.jpg")
    add_receipt(tmp_path, "b.jpg", {**VALID, "lines": [{"name": "MAITO", "amount_cents": 125}]})

    main(["run", "--dir", str(tmp_path), "--variant", "ocr:n", "--subset", "full"], deps())

    assert [p.name for p in (tmp_path / "results" / RUN_ID / "ocr-n").iterdir()] == ["2.json"]


# --- AC18: privacy ----------------------------------------------------------------------

MARKER = "SECRET-CONTENT"


def test_ac18_output_and_summary_contain_no_receipt_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    secret_truth = {
        "store": f"{MARKER} store",
        "date": "2026-01-02",
        "total_cents": 125,
        "line_count": 1,
        "lines": [{"name": f"{MARKER} line", "amount_cents": 125}],
    }
    add_receipt(tmp_path, f"{MARKER}-1.jpg", secret_truth)
    add_receipt(tmp_path, f"{MARKER}-2.jpg", secret_truth)
    add_receipt(tmp_path, f"{MARKER}-3.jpg", truth=None)
    secret_answer = RIGHT_ANSWER.replace("MAITO", MARKER)
    reader = FakeReader(results=[ReadResult(text=secret_answer), ReadResult(text=MARKER)])

    code = main(
        ["run", "--dir", str(tmp_path), "--variant", "ocr:m", "--variant", "vision:v"],
        deps(reader, FakeOcr(text=f"{MARKER} 1,25")),
    )

    assert code == 0
    printed = output(capsys)
    summary = (tmp_path / "results" / RUN_ID / "summary.md").read_text(encoding="utf-8")
    for text in (printed, summary):
        assert MARKER not in text
        assert ".jpg" not in text
    details = (tmp_path / "results" / RUN_ID / "ocr-m" / "1.json").read_text(encoding="utf-8")
    assert MARKER in details


# --- AC19: only the configured Ollama ---------------------------------------------------


def test_ac19_default_reader_uses_the_ollama_setting(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_OLLAMA_URL", "http://host.docker.internal:11434")

    built = default_deps(Settings())

    assert isinstance(built.reader, OllamaReader)
    assert built.reader.base_url == "http://host.docker.internal:11434"
    assert isinstance(built.ocr, TesseractOcr)


@pytest.mark.parametrize(
    ("first", "second"), [("ocr:m", "ocr:m"), ("ocr:a:b", "ocr:a-b"), ("vision:v", "vision:v")]
)
def test_ac9_repeated_variant_is_refused_before_ollama(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], first: str, second: str
) -> None:
    reader = FakeReader()

    code = main(
        ["run", "--dir", str(tmp_path), "--variant", first, "--variant", second], deps(reader)
    )

    assert code == 2
    assert output(capsys).strip() == f"Duplicate variant: {second}"
    assert reader.events == []


class BrokenReader(FakeReader):
    def read(self, model: str, prompt: str, image: bytes | None) -> ReadResult:
        if self.reads:
            raise RuntimeError(f"{MARKER} {MARKER}-2.jpg")
        return super().read(model, prompt, image)


def test_ac21_unexpected_error_prints_only_its_type(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_receipt(tmp_path, f"{MARKER}-1.jpg")
    add_receipt(tmp_path, f"{MARKER}-2.jpg")

    code = main(["run", "--dir", str(tmp_path), "--variant", "vision:v"], deps(BrokenReader()))

    assert code == 3
    printed = output(capsys)
    assert printed.strip().splitlines()[-1] == "Evaluation failed: RuntimeError"
    assert MARKER not in printed
    assert "Traceback" not in printed
    assert (tmp_path / "results" / RUN_ID / "vision-v" / "1.json").exists()


def test_ac1_module_runs_from_the_command_line(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"image")
    backend = Path(__file__).resolve().parents[2]

    result = subprocess.run(  # noqa: S603 - the test's own interpreter and module
        [sys.executable, "-m", "evaluation", "init", "--dir", str(tmp_path)],
        cwd=backend,
        capture_output=True,
        text=True,
        check=False,
    )

    assert (result.returncode, result.stdout.strip()) == (0, "Created 1 template(s).")
