"""Host header check: refuses a request whose Host is not a known name of this app."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app import texts
from app.errors import error_response

# A page that rebinds its own name to 127.0.0.1 is the backend's origin for the browser, so
# CORS does not stop it; only its Host header gives it away. `backend` and `backend-e2e` are
# the Compose service names, which Vite's proxy sends as the Host.
_KNOWN_HOSTS = frozenset({"127.0.0.1", "localhost", "backend", "backend-e2e"})


def add_host_check(app: FastAPI) -> None:
    """Answer 400 `invalid_host` to a request with an unknown Host header."""

    @app.middleware("http")
    async def check_host(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        name = request.headers.get("host", "").partition(":")[0].casefold()
        if name not in _KNOWN_HOSTS:
            return error_response("invalid_host", texts.INVALID_HOST, 400)
        return await call_next(request)
