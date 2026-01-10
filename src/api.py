"""External API integration module for fetching financial data.

This module handles the retrieval of financial data from external sources,
specifically fetching the S&P 500 ticker list from Wikipedia and downloading
historical market data using the Yahoo Finance API.
"""

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from io import StringIO
from typing import List, Optional

def get_sp500_tickers() -> List[str]:
    """Retrieves the current list of S&P 500 tickers from Wikipedia.

    Performs an HTTP GET request to the Wikipedia page for the S&P 500 index,
    parses the constituents table, and sanitizes the ticker symbols (e.g.,
    replacing dots with dashes) for compatibility with Yahoo Finance.

    Returns:
        List[str]: An alphabetically sorted list of ticker symbols. Returns
            an empty list if the request fails or parsing errors occur.
    """

    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        tickers = []
        for t in df['Symbol'].tolist():
            tickers.append(t.replace('.', '-'))

        print(f"Success: {len(tickers)} tickers retrieved.")
        return sorted(tickers)

    except Exception as e:
        print(f"Technical error retrieving tickers: {e}")
        return []

def download_new_data(
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
        ) -> pd.DataFrame:
    """Downloads historical price data for a specific ticker via Yahoo Finance.

    This function acts as a wrapper for `yfinance.download`. It manages the
    start and end dates to avoid downloading redundant data. If a `start_date`
    is provided, data retrieval begins from the following day.

    Args:
        ticker (str): The asset ticker symbol (e.g., "AAPL").
        start_date (Optional[str]): The start date in ISO format (YYYY-MM-DD).
            If None, the full available history is downloaded.
        end_date (Optional[str]): The end date in ISO format (YYYY-MM-DD).
            Data is fetched up to this date (exclusive). If None, downloads
            up to the most recent available data.

    Returns:
        pd.DataFrame: A DataFrame containing historical market data (Open, High,
            Low, Close, Volume). Returns an empty DataFrame if the calculated
            start date is in the future.
    """

    if start_date == None:
        if end_date == None:
            return yf.download(
                ticker,
                interval="1d",
                progress=False,
                auto_adjust=True
            )
        else:
            return yf.download(
                ticker,
                interval="1d",
                progress=False,
                auto_adjust=True,
                end=end_date
            )

    start = datetime.fromisoformat(start_date) + timedelta(days=1)

    if start >= datetime.now():
        return pd.DataFrame()

    start_str = start.strftime("%Y-%m-%d")

    if end_date == None:
        return yf.download(
            ticker,
            start=start_str,
            interval="1d",
            progress=False,
            auto_adjust=True
        )
    else:
        return yf.download(
            ticker,
            start=start_str,
            interval="1d",
            progress=False,
            auto_adjust=True,
            end=end_date
        )