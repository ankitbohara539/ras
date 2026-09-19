from dataclasses import dataclass


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication is required.") -> None:
        super().__init__("AUTHENTICATION_ERROR", message, 401)


class AuthorizationError(AppError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__("AUTHORIZATION_ERROR", message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__("NOT_FOUND", message, 404)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("CONFLICT", message, 409)
