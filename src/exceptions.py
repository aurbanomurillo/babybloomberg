"""
Custom exceptions for error handling and flow control.

This module defines the application's own exception hierarchy, covering
database errors, resource shortages (cash/stock), invalid operation states,
and flow control signals for strategies.
"""

class DatabaseError(Exception):
    """Base exception for SQLite database-related errors."""

    pass

class TickerUpToDateError(DatabaseError):
    """Indicates that an attempt was made to update a ticker that is already up to date."""

    pass

class NotEnoughError(Exception):
    """Base exception for resource shortage errors (insufficient funds or stock)."""

    pass

class NotEnoughCashError(NotEnoughError):
    """Raised when attempting to buy without sufficient available capital (fiat)."""

    pass

class NotEnoughStockError(NotEnoughError):
    """Raised when attempting to sell a larger quantity of stock than is currently owned."""

    pass

class TradeNotClosed(Exception):
    """Raised when attempting to calculate profits or returns on a trade that is still open."""

    pass

class StopChecking(Exception):
    """Flow control exception used to stop a strategy's iteration.

    Used similarly to a 'break' signal when a strategy determines it does not
    need to evaluate subsequent dates (e.g., after closing a position in BoundedStrategy).
    """

    pass

class NotValidIntervalError(Exception):
    """Raised when an invalid time interval or threshold is provided.

    Examples: an unknown date format or an impossible percentage drop (less than -100%).
    """

    pass
