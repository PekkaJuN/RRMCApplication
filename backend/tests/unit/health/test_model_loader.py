import logging
from collections.abc import Callable

import pytest

from app.engines.model import ModelCheckResult, ModelLoadError
from app.health.service import ModelLoader


class ScriptedModel:
    """A model whose check results and load outcomes are given in advance."""

    def __init__(self, checks: list[ModelCheckResult], loads_fail: list[bool]) -> None:
        self._checks = checks
        self._loads_fail = loads_fail
        self.load_calls = 0

    def check(self) -> ModelCheckResult:
        return self._checks.pop(0)

    def load(self) -> None:
        self.load_calls += 1
        if self._loads_fail.pop(0):
            raise ModelLoadError("Loading model test-model failed")


def run_now(work: Callable[[], None]) -> None:
    work()


def test_ac17_start_loads_an_available_model_once() -> None:
    model = ScriptedModel(checks=["ok"], loads_fail=[False])
    loader = ModelLoader(model, run_in_background=run_now)

    loader.start()
    loader.on_model_ok()

    assert model.load_calls == 1


def test_ac18_start_without_model_loads_on_first_ok_check() -> None:
    model = ScriptedModel(checks=["unavailable"], loads_fail=[False])
    loader = ModelLoader(model, run_in_background=run_now)

    loader.start()
    assert model.load_calls == 0

    loader.on_model_ok()
    loader.on_model_ok()
    assert model.load_calls == 1


def test_ac18_failed_load_warns_and_is_retried(caplog: pytest.LogCaptureFixture) -> None:
    model = ScriptedModel(checks=["ok"], loads_fail=[True, False])
    loader = ModelLoader(model, run_in_background=run_now)

    loader.start()
    loader.on_model_ok()

    assert model.load_calls == 2
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["Loading model test-model failed; retrying on the next health check"]


def test_ac17_no_second_load_while_loading() -> None:
    pending: list[Callable[[], None]] = []
    model = ScriptedModel(checks=["ok"], loads_fail=[False])
    loader = ModelLoader(model, run_in_background=pending.append)

    loader.start()
    loader.on_model_ok()

    assert len(pending) == 1
