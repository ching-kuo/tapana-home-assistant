"""Exceptions for the sony_mflight library."""


class SonyMflightError(Exception):
    """Base exception for all sony_mflight errors."""


class AuthenticationError(SonyMflightError):
    """Raised when Cognito authentication fails."""


class TokenExpiredError(AuthenticationError):
    """Raised when tokens have expired and refresh also failed."""


class ApiError(SonyMflightError):
    """Raised when the AppSync API returns an error."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class CommandError(ApiError):
    """Raised when a device command is rejected (errorCode != null)."""


class DeviceOfflineError(SonyMflightError):
    """Raised when the device is not connected to the cloud."""


class InvalidParamsError(SonyMflightError):
    """Raised when invalid parameters are provided to a method."""
