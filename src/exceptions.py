"""Custom exceptions for error handling and flow control.

This module defines the application's own exception hierarchy, covering
database errors, resource shortages (cash/stock), invalid operation states,
and flow control signals for strategies.
"""


class DatabaseError(Exception):
    """Base exception class for errors related to database operations."""

    pass


class TickerUpToDateError(DatabaseError):
    """Raised when an update is attempted on a ticker that is already current.

    This exception indicates that the local database already contains the most
    recent available data for the specified asset, making a download unnecessary.
    """

    pass


class NotEnoughError(Exception):
    """Base exception class for resource shortage scenarios (insufficient funds or inventory)."""

    pass


class NotEnoughCashError(NotEnoughError):
    """Raised when a buy order cannot be executed due to insufficient liquid capital.

    This occurs when the strategy attempts to purchase an asset but the available
    fiat balance is lower than the required transaction amount.
    """

    pass


class NotEnoughStockError(NotEnoughError):
    """Raised when a sell order cannot be executed due to insufficient asset holdings.

    This occurs when the strategy attempts to sell a quantity of an asset that
    exceeds the currently owned inventory.
    """

    pass


class TradeNotClosed(Exception):
    """Raised when an operation requiring a closed trade state is attempted on an active position.

    This is typically raised when trying to calculate realized profits (PnL) or
    final returns on a trade that has not yet been exited.
    """

    pass


class StopChecking(Exception):
    """Signal exception used to terminate the iterative evaluation loop of a strategy.

    This exception is used for flow control rather than error handling. It allows
    a strategy (e.g., `BoundedStrategy`) to signal the orchestrator to stop
    processing subsequent dates because a terminal condition (like a Stop Loss
    or Take Profit) has been met.
    """

    pass


class NotValidIntervalError(Exception):
    """Raised when an invalid time interval or calculation threshold is encountered.

    Examples include unrecognizable date formats or mathematically impossible
    thresholds (e.g., a percentage drop greater than 100%).
    """

    pass