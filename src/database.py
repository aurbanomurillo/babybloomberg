"""
SQLite-based financial data persistence management.

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

    Uses pandas 'to_sql' for optimized bulk insertion.
    If the table exists, new data is appended; otherwise, the table is created.

    Args:
        table_name (str): Table name (usually the asset ticker).
        df (pd.DataFrame): Data to save. The index (Date) will be saved as a column.
        db_name (str, optional): Path to the .db file. Defaults to 'data/market_data.db'.
    """

    with sqlite3.connect(db_name) as connection:
        df.to_sql(table_name, connection, if_exists='append', index=True)
        connection.commit()

def load_stock(ticker:str) -> None:
    """Updates or downloads the full history of a specific asset.

    Checks the last available date in the local database for that ticker.
    If data exists, it downloads only the differential (delta) since the last date.
    If not, it downloads the full history. New data is cleaned and saved.

    Args:
        ticker (str): Symbol of the asset to update (e.g., "AAPL").
    """

    if not os.path.exists('data/market_data.db'):
        print("Data file not found. Creating a new one.")
    try:
        last_date = get_last_date(ticker)
        data = download_new_data(ticker, last_date)

        if data.empty:
            # print(f"{ticker}: already updated")
            return None

        clean_data = round_price(data)
        save_to_db(ticker, clean_data)

        # print(f"{ticker}: updated from {clean_data['Date'].iloc[0]} to {clean_data['Date'].iloc[-1]}")
    except Exception as e:
        print(f"{ticker} failed: {e}")

def load_stocks(ticker_list: list[str]) -> None:
    """Executes bulk loading and updating for a list of assets.

    Iterates over the provided list invoking `load_stock` for each element.
    Displays a visual progress bar in the console.

    Args:
        ticker_list (list[str]): List of symbols to process.
    """

    for ticker in track(ticker_list, description="Saving data..."):
        load_stock(ticker)
    
def get_first_date(
        ticker: str | StockFrame,
        db_path: str = 'data/market_data.db'
        ) -> str | None:
    """Retrieves the earliest available date for an asset.

    Can query the database directly (if a ticker string is passed)
    or inspect a StockFrame object already loaded in memory.

    Args:
        ticker (str | StockFrame): Asset symbol or data object.
        db_path (str, optional): Path to the database (only if ticker is str).

    Returns:
        str | None: Date in "YYYY-MM-DD" format or None if no data exists or connection fails.
    """
    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, db_path)

            return df.index[0]
        elif isinstance(ticker, StockFrame):
            return ticker.index[0]

    except (pd.errors.DatabaseError, sqlite3.OperationalError) as e:
        return None

def get_last_date(
        ticker: str | StockFrame,
        db_path: str = 'data/market_data.db'
        ) -> str | None:
    """Retrieves the most recent available date for an asset.

    Useful for determining from which point new data should be downloaded.
    Works by both querying SQL and inspecting an in-memory StockFrame.

    Args:
        ticker (str | StockFrame): Asset symbol or data object.
        db_path (str, optional): Path to the database.

    Returns:
        str | None: Date in "YYYY-MM-DD" format or None if no data exists or connection fails.
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

    Reads the table corresponding to the ticker, removes duplicates by date, and ensures
    that numeric columns (Open, High, Low, Close, Adj Close) have the correct type.
    Allows filtering by date range optionally.

    Args:
        ticker (str): Symbol of the table/asset to read.
        db_path (str, optional): Path to the database.
        start (str | None, optional): Filter start date (inclusive).
        end (str | None, optional): Filter end date (inclusive).

    Returns:
        StockFrame: Object with clean historical data indexed by date.
    """

    with sqlite3.connect(db_path) as connection:
        query = f"""
            SELECT * 
            FROM 
            {ticker}"""        
        df = pd.read_sql_query(query, connection)
    
    if 'Date' in df.columns:
        df = df.drop_duplicates(subset=['Date'], keep='last')
        df.set_index('Date', inplace=True)
        
        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]
       
    cols_to_fix = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
            
    return StockFrame(df)

def get_existing_tickers(db_path: str = 'data/market_data.db') -> list[str]:

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