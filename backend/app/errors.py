"""API error format: every error response is `{"error": code, "message": Finnish text}`."""

import logging

from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import texts

logger = logging.getLogger(__name__)


class AppError(Exception):
    """An expected failure with a stable error code, a Finnish message and an HTTP status."""

    def __init__(self, code: str, message: str, status: int) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status


def error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _handle_app_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)  # noqa: S101 - registered for AppError only
    return error_response(exc.code, exc.message, exc.status)


async def _handle_http_error(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - registered for it only
    if exc.status_code == 404:
        return error_response("not_found", texts.NOT_FOUND, 404)
    return await http_exception_handler(request, exc)


def _handle_validation_error(request: Request, exc: Exception) -> Response:
    # The validation details can echo the request body, so they are not returned or logged.
    return error_response("invalid_request", texts.INVALID_REQUEST, 422)


def _handle_unexpected_error(request: Request, exc: Exception) -> Response:
    # Starlette calls this handler outside the except block, so the exception is passed on.
    logger.error("Unexpected error in %s %s", request.method, request.url.path, exc_info=exc)
    return error_response("internal_error", texts.INTERNAL_ERROR, 500)


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
