"""SQLite-based financial data persistence management.

This module handles all input/output operations with the local database.
It includes functions to save DataFrames, load updated historical data from the API,
and retrieve clean data in `StockFrame` format for use in strategies.
"""

import sqlite3
import pandas as pd
import os
from rich.progress import track
from src.api import *
from src.processing import *
from src.exceptions import *
from src.stockframe_manager import *

def save_to_db(
        table_name: str,
        df: pd.DataFrame,
        db_name: str = 'data/market_data.db'
        ) -> None:
    """Persists a DataFrame into a specific table in the SQLite database.

    Uses pandas `to_sql` for optimized bulk insertion. If the table already
    exists, the new data is appended; otherwise, the table is created.

    Args:
        table_name (str): The name of the table (typically the asset ticker).
        df (pd.DataFrame): The data to save. The index (Date) will be included
            as a column in the database.
        db_name (str, optional): The file path to the SQLite database.
            Defaults to 'data/market_data.db'.
    """
    
    with sqlite3.connect(db_name) as connection:
        df.to_sql(table_name, connection, if_exists='append', index=True)
        connection.commit()

def load_stock(ticker: str) -> None:
    """Updates or downloads the full history of a specific asset.

    Checks the last available date in the local database for the given ticker.
    If data exists, it downloads only the differential (delta) since that date.
    If no data exists, it downloads the full history. The new data is cleaned,
    the profit column is calculated, and it is saved to the database.

    Args:
        ticker (str): The symbol of the asset to update (e.g., "AAPL").
    """

    if not os.path.exists('data/market_data.db'):
        print("Data file not found. Creating a new one.")
    try:
        last_date = get_last_date(ticker)
        data = download_new_data(ticker, last_date)

        if data.empty:
            return None

        clean_data = round_price(data)
        
        if not clean_data.empty:
            initial_price = clean_data['Close'].iloc[0]
            if initial_price != 0:
                clean_data['Profit'] = clean_data['Close'] / initial_price
            else:
                clean_data['Profit'] = 0.0

        save_to_db(ticker, clean_data)

    except Exception as e:
        print(f"{ticker} failed: {e}")

def load_stocks(ticker_list: list[str]) -> None:
    """Executes bulk loading and updating for a list of assets.

    Iterates over the provided list, invoking `load_stock` for each element.
    Displays a visual progress bar in the console using `rich`.

    Args:
        ticker_list (list[str]): A list of ticker symbols to process.
    """

    for ticker in track(ticker_list, description="Saving data..."):
        load_stock(ticker)
    
def get_first_date(
        ticker: str | StockFrame,
        db_path: str = 'data/market_data.db'
        ) -> str | None:
    """Retrieves the earliest available date for an asset.

    This function can query the database directly (if a ticker string is passed)
    or inspect a `StockFrame` object already loaded in memory.

    Args:
        ticker (str | StockFrame): The asset symbol or the data object.
        db_path (str, optional): The path to the database (used only if
            `ticker` is a string). Defaults to 'data/market_data.db'.

    Returns:
        str | None: The date in "YYYY-MM-DD" format, or None if no data
            exists or a connection error occurs.
    """

    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, db_path)

            return df.index[0]
        elif isinstance(ticker, StockFrame):
            return ticker.index[0]

    except (pd.errors.DatabaseError, sqlite3.OperationalError):
        return None

def get_last_date(
        ticker: str | StockFrame,
        db_path: str = 'data/market_data.db'
        ) -> str | None:
    """Retrieves the most recent available date for an asset.

    Useful for determining the starting point for downloading new data.
    Works by either querying SQL or inspecting an in-memory `StockFrame`.

    Args:
        ticker (str | StockFrame): The asset symbol or the data object.
        db_path (str, optional): The path to the database.
            Defaults to 'data/market_data.db'.

    Returns:
        str | None: The date in "YYYY-MM-DD" format, or None if no data
            exists or a connection error occurs.
    """

    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, db_path)

            return df.index[-1]
        elif isinstance(ticker, StockFrame):
            return ticker.index[-1]

    except (pd.errors.DatabaseError, sqlite3.OperationalError): 
        return None

def get_sf_from_sqlite(
        ticker: str,
        db_path: str = 'data/market_data.db',
        start: str | None = None,
        end: str | None = None
        ) -> StockFrame:
    """Retrieves asset data from the database and constructs a StockFrame.

    Reads the table corresponding to the ticker, removes duplicates based on the
    date, and ensures that numeric columns (Open, High, Low, Close, Adj Close)
    are correctly typed. It also supports optional date range filtering.

    Args:
        ticker (str): The symbol of the table/asset to read.
        db_path (str, optional): The path to the database.
            Defaults to 'data/market_data.db'.
        start (str | None, optional): The start date for filtering (inclusive).
            Defaults to None.
        end (str | None, optional): The end date for filtering (inclusive).
            Defaults to None.

    Returns:
        StockFrame: An object containing the clean historical data, indexed by date.
    """

    with sqlite3.connect(db_path) as connection:
        query = f"""
            SELECT * FROM 
            {ticker}"""        
        df = pd.read_sql_query(query, connection)
    
    if 'Date' in df.columns:
        df = df.drop_duplicates(subset=['Date'], keep='last')
        df.set_index('Date', inplace=True)
        
        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]
       
    cols_to_fix = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Profit']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
            
    return StockFrame(df)

def get_existing_tickers(db_path: str = 'data/market_data.db') -> list[str]:
    """Retrieves a list of all ticker symbols currently stored in the database.

    Connects to the SQLite database and queries the master table to identify
    all user-created tables, excluding internal SQLite tables.

    Args:
        db_path (str, optional): The file path to the SQLite database.
            Defaults to 'data/market_data.db'.

    Returns:
        list[str]: An alphabetically sorted list of ticker symbols. Returns an
            empty list if the database does not exist or an error occurs.
    """

    if not os.path.exists(db_path):
        return []
        
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            ticker_list = [t[0] for t in tables if not t[0].startswith('sqlite_')]
            return sorted(ticker_list)
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []