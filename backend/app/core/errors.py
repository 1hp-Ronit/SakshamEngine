"""One error shape for the whole API: {"error": {"code": "...", "message": "..."}}."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger("errors")


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFound(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(code, message, 404)


class ConsentError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 403):
        super().__init__(code, message, status_code)


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 403: "FORBIDDEN"}.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        fields = [".".join(str(p) for p in e["loc"] if p != "body") + ": " + e["msg"] for e in exc.errors()]
        return JSONResponse(error_body("VALIDATION_ERROR", "; ".join(fields)), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)  # message scrubbed by SecretFilter
        return JSONResponse(error_body("INTERNAL_ERROR", "Something went wrong. Please try again."), status_code=500)
