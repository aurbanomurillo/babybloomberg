"""
Data structure for recording individual trading operations.

This module defines the `Operation` class, which serves as an audit log entry
for every transaction (buy or sell) attempted by a strategy. It stores details
such as price, date, success status, and the trigger reason.
"""

class Operation:
    """Represents a single trading event (Buy or Sell).

    Stores all relevant metadata about a transaction, including whether it was
    successful or failed due to lack of resources.

    Attributes:
        type (str): Type of operation (e.g., "buy", "sell").
        cash_amount (float): Total value of the operation in cash.
        ticker (str): Asset symbol.
        stock_price (float): Price per share at the moment of execution.
        successful (bool): True if the trade was executed, False if rejected (e.g., insufficient funds).
        date (str): Date of execution (YYYY-MM-DD).
        trigger (str): The reason or event that triggered this operation (e.g., "stop_loss", "manual").
    """

    def __init__(
            self,
            type: str,
            cash_amount: float,
            ticker: str,
            stock_price: float,
            successful: bool,
            date: str,
            trigger: str = "manual"
            ):
        """Initializes a new operation record.

        Args:
            type (str): Operation type ("buy"/"sell").
            cash_amount (float): Total monetary value involved.
            ticker (str): Asset symbol.
            stock_price (int | float): Share price at execution.
            successful (bool): Execution status.
            date (str): Date string.
            trigger (str, optional): Cause of the trade. Defaults to "manual".
        """

        self.type: str = type
        self.cash_amount: float = float(cash_amount)
        self.ticker: str = ticker
        self.stock_price: int = stock_price
        self.successful: bool = successful
        self.date: str = date
        self.trigger: str = trigger
        
    def get_description(self) -> str:
        """Generates a human-readable summary of the operation.

        Returns:
            str: A formatted string describing the operation's success, type,
                reason, value, asset, price, and date.
        """
        
        if self.successful:  
            return f"Successful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.date}"
        else:
            return f"Unsuccessful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.date}"
