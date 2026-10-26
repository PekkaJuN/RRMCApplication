"""Logging to standard output."""

import logging
import sys
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

_HANDLER_NAME = "rrmc-stdout"
_request_logger = logging.getLogger("app.requests")


def configure_logging(level: str) -> None:
    """Send log records at `level` and above to standard output.

    Replaces only the handler added by an earlier call, so handlers installed by others
    (for example pytest's log capture) stay in place.
    """
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)


def add_request_logging(app: FastAPI) -> None:
    """Log one line per request: method, path, status and duration.

    The query string and the bodies are never logged; they can contain receipt content.
    """

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        # An exception passes through here and becomes a 500 response further out.
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000)
            _request_logger.info(
                "%s %s %d %dms", request.method, request.url.path, status, duration_ms
            )
