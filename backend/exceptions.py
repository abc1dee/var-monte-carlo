"""
Custom exception classes for the VaR Monte Carlo API.

Each exception maps to a specific HTTP status code and carries a structured
error_code that the client can use for programmatic error handling.

Usage in route handlers:
    from exceptions import InvalidTickerError, DataFetchError, SimulationError

    raise InvalidTickerError("NVDA123 is not a valid ticker symbol.")

Usage in main.py (register handlers once):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from exceptions import InvalidTickerError, DataFetchError, SimulationError

    @app.exception_handler(InvalidTickerError)
    async def invalid_ticker_handler(request: Request, exc: InvalidTickerError):
        return JSONResponse(status_code=exc.status_code,
                            content={"detail": exc.message, "error_code": exc.error_code})
"""

from fastapi import HTTPException


class AppBaseError(HTTPException):
    """
    Base class for all application-level exceptions.

    Extends FastAPI's HTTPException so it can be raised anywhere in the
    call stack and caught by a registered exception handler in main.py.
    Adds `message` and `error_code` attributes on top of the standard
    `status_code` and `detail`.
    """

    status_code: int = 500        # subclasses override this
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        self.message = message
        self.error_code = self.__class__.error_code
        # Pass message as `detail` so FastAPI's built-in error handling
        # also works correctly if no custom handler is registered.
        super().__init__(status_code=self.__class__.status_code, detail=message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code}, "
            f"error_code={self.error_code!r}, "
            f"message={self.message!r})"
        )


class InvalidTickerError(AppBaseError):
    """
    Raised when the supplied ticker symbol cannot be resolved to a tradeable
    security in Yahoo Finance.

    HTTP mapping: 400 Bad Request
    Error code:   INVALID_TICKER
    """

    status_code = 400
    error_code = "INVALID_TICKER"


class DataFetchError(AppBaseError):
    """
    Raised when the yfinance API call succeeds at the network level but
    returns empty or unusable data, or when the network call itself fails
    due to a timeout, DNS error, or Yahoo Finance being unreachable.

    HTTP mapping: 503 Service Unavailable
    Error code:   DATA_SOURCE_UNAVAILABLE
    """

    status_code = 503
    error_code = "DATA_SOURCE_UNAVAILABLE"


class SimulationError(AppBaseError):
    """
    Raised when the quant engine encounters an unexpected error during the
    Monte Carlo simulation (e.g. numerical instability, malformed input that
    passed schema validation, etc.).

    HTTP mapping: 500 Internal Server Error
    Error code:   INTERNAL_ERROR
    """

    status_code = 500
    error_code = "INTERNAL_ERROR"