"""Typed error hierarchy.

Every failure raised by a service or a route is an `AppError` subclass carrying a
stable machine-readable `code`, a human `message` and an HTTP `status_code`.
Services and routes must never raise bare `Exception`/`ValueError`; the boundary
test suite and ruff's `TRY`/`EM` rules both police this.

Note on naming: the brief specifies `statusCode`. Python attribute names are
snake_case (pylint `invalid-name` would reject the camelCase form), so the
attribute is `status_code` and the *wire* representation stays camelCase-free
JSON under an `error` envelope. See `AppError.to_payload`.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "AppError",
    "ConflictError",
    "DependencyError",
    "ForbiddenError",
    "InternalError",
    "NotFoundError",
    "ReadOnlyModuleError",
    "ValidationError",
]


class AppError(Exception):
    """Base class for every expected failure in the system."""

    code: str = "internal_error"
    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        """Render the JSON body returned to clients."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class ValidationError(AppError):
    code = "validation_failed"
    status_code = 422
    default_message = "The request payload failed validation."


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    default_message = "The requested resource does not exist."

    @classmethod
    def for_resource(cls, resource: str, resource_id: str) -> NotFoundError:
        return cls(
            f"{resource} {resource_id!r} was not found.",
            details={"resource": resource, "id": resource_id},
        )


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    default_message = "The resource is not in a state that allows this operation."


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403
    default_message = "The caller may not perform this operation."


class ReadOnlyModuleError(ForbiddenError):
    """Raised when another module attempts to mutate staff records."""

    code = "read_only_module"
    default_message = "The staff module is read-only to other modules."


class DependencyError(AppError):
    code = "dependency_unavailable"
    status_code = 503
    default_message = "A downstream dependency is unavailable."


class InternalError(AppError):
    """Explicit stand-in for an unexpected fault, so nothing raises bare errors."""

    code = "internal_error"
    status_code = 500
