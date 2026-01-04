"""
Data processing and date manipulation utilities.

This module provides helper functions to clean financial data (rounding prices),
extract specific price points, and handle date arithmetic (generating ranges
or subtracting natural language time intervals like '3 days').
"""

import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from src.exceptions import *
from src.stockframe_manager import *

def round_price(data: pd.DataFrame) -> pd.DataFrame | StockFrame:
    """Rounds financial data columns to two decimal places.

    Standardizes the format of the DataFrame by ensuring the index is named "Date"
    and rounding typical price columns (Open, High, Low, Close, Adj Close).
    Handles potential MultiIndex structures returned by some data sources.

    Args:
        data (pd.DataFrame | StockFrame): Raw data containing price history.

    Returns:
        pd.DataFrame | StockFrame: The processed DataFrame with rounded float values.
            Returns the original object if it is empty.
    """

    if data.empty:
        return data

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    data.index.name = "Date" 
    price_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    
    for col in price_columns:
        if col in data.columns:
            data[col] = data[col].astype(float).round(2)
    
    data.index = data.index.astype(str)
    return data

def get_price_in(
        df: StockFrame | pd.DataFrame,
        date: str
        ) -> float:
    """Retrieves the closing price for a specific date.

    A helper function to safely extract the 'Close' value from the data source.

    Args:
        df (StockFrame | pd.DataFrame): The data source.
        date (str): The date to query (YYYY-MM-DD).

    Returns:
        float: The closing price on the specified date.
    """

    return float(df.loc[date]['Close'])

def get_date_range(
        start_str: str, 
        end_str: str
        ) -> list[str]:
    """Generates a list of date strings between a start and end date (inclusive).

    Args:
        start_str (str): Start date (YYYY-MM-DD).
        end_str (str): End date (YYYY-MM-DD).

    Returns:
        list[str]: A list of strings representing every day in the range.
    """

    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    
    date_list = []
    current = start
    
    while current <= end:
        date_list.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
        
    return date_list

def subtract_interval(
        date_str: str,
        interval_str: str
        ) -> str:
    """Subtracts a natural language time interval from a given date.

    Parses strings like "1 day", "2 weeks", "3 months" and calculates the
    resulting past date.

    Args:
        date_str (str): The reference date (YYYY-MM-DD).
        interval_str (str): The interval to subtract (e.g., "5 days", "1 year").

    Returns:
        str: The resulting past date in "YYYY-MM-DD" format.

    Raises:
        NotValidIntervalError: If the unit (day, week, month, year) is not recognized.
    """
    
    date_dt = datetime.strptime(date_str, "%Y-%m-%d")
    
    parts = interval_str.split()
    amount = int(parts[0])
    unit = parts[1].lower()
    if 'd' in unit:
        delta = relativedelta(days=amount)
    elif 'w' in unit:
        delta = relativedelta(weeks=amount)
    elif  'm' in unit:
        delta = relativedelta(months=amount)
    elif 'y' in unit:
        delta = relativedelta(years=amount)
    else:
        raise NotValidIntervalError("Unrecognized unit (use day, week, month, year)")

    new_date = date_dt - delta

    return new_date.strftime("%Y-%m-%d")
