"""Custom DataFrame specialization for financial time series management.

This module defines the `StockFrame` class, which extends the standard pandas
DataFrame. It adds specific functionality for safely retrieving stock prices
and handling data gaps (e.g., weekends or holidays) by searching for the last
valid known price.
"""

import pandas as pd
from datetime import datetime, timedelta

class StockFrame(pd.DataFrame):
    """A pandas DataFrame extension optimized for financial time series data.

    This class provides specialized methods to handle common issues in financial
    datasets, such as missing entries due to market holidays or weekends. It
    ensures that data retrieval operations fail gracefully or return the most
    recent valid data point.
    """

    @property
    def _constructor(self):
        """Internal property to ensure slice/manipulation returns StockFrame instances.

        Overrides the standard pandas constructor property so that operations
        performed on a StockFrame (like slicing) return a StockFrame object
        instead of a generic pandas DataFrame.

        Returns:
            type: The StockFrame class reference.
        """

        return StockFrame

    def get_price_in(
            self, 
            date: str
            ) -> float | None:
        """Retrieves the closing price for a specific date.

        Safely attempts to access the 'Close' column for the given index.
        Returns None instead of raising an error if the date is not found.

        Args:
            date (str): The target date in "YYYY-MM-DD" format.

        Returns:
            float | None: The closing price if the date exists, otherwise None.
        """

        try:
            return float(self.loc[date]['Close'])
        except KeyError:
            # print(f"Error: Date {date} not found in data.").
            return None
    
    def get_last_valid_price(
            self,
            target_date_str: str
            ) -> float | None:
        """Finds the most recent valid closing price on or before a target date.

        Useful for getting a reference price when the target date falls on a
        weekend or holiday. It iterates backwards from the `target_date_str`
        until it finds a date with available data in the index.

        Args:
            target_date_str (str): The starting date for the backward search (YYYY-MM-DD).

        Returns:
            float | None: The price of the last valid trading day found, or None
                if the search goes back past the beginning of the dataset.
        """
        
        first_available_date = self.index[0] 
        current_date_str = target_date_str
        
        while current_date_str >= first_available_date:
            
            price = self.get_price_in(current_date_str)
            
            if not price == None:
                return price
            
            current_date_dt = datetime.strptime(current_date_str, "%Y-%m-%d")
            previous_date_dt = current_date_dt - timedelta(days=1)
            current_date_str = previous_date_dt.strftime("%Y-%m-%d")

        return None