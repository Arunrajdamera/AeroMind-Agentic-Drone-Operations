from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from aeromind.api.errors import domain_error_spec
from aeromind.core.exceptions import DomainError
from aeromind.schemas.api import ApiErrorResponse, ApiValidationIssue

logger = logging.getLogger(__name__)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[ApiValidationIssue] | None = None,
) -> JSONResponse:
    body = ApiErrorResponse(
        code=code,
        message=message,
        details=details or [],
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        ApiValidationIssue(
            location=[
                str(item) if isinstance(item, str) else item
                for item in error["loc"]
            ],
            type=error["type"],
            message=error["msg"],
        )
        for error in exc.errors()
    ]

    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details=details,
    )


async def domain_error_exception_handler(
    request: Request,
    exc: DomainError,
) -> JSONResponse:
    spec = domain_error_spec(exc)

    return _error_response(
        status_code=spec.status_code,
        code=spec.code,
        message=str(exc) or "The requested operation could not be completed.",
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    message = (
        exc.detail
        if isinstance(exc.detail, str)
        else "The request could not be completed."
    )

    code_by_status = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
    }

    return _error_response(
        status_code=exc.status_code,
        code=code_by_status.get(exc.status_code, "HTTP_ERROR"),
        message=message,
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError,
) -> JSONResponse:
    logger.exception("Database operation failed")

    return _error_response(
        status_code=500,
        code="DATABASE_ERROR",
        message="A database error occurred.",
    )


async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled application error")

    return _error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An internal server error occurred.",
    )
