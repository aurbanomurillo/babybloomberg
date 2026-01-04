"""
External API integration module for fetching financial data.

This module manages connections with external data sources, primarily
Yahoo Finance (via `yfinance`) and Wikipedia, to retrieve asset lists
and historical price time series.
"""

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from io import StringIO


def get_sp500_tickers() -> list[str]:
    """Retrieves the updated list of S&P 500 tickers from Wikipedia.

    Performs an HTTP request to the S&P 500 Wikipedia page, extracts the components
    table, and processes the symbols to ensure compatibility with Yahoo Finance
    (e.g., replacing dots '.' with dashes '-').

    Returns:
        list[str]: An alphabetically sorted list of strings, where each string
            is the symbol (ticker) of an S&P 500 company. Returns an empty
            list `[]` if a request or parsing error occurs.
    """

    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers = headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        tickers = []
        for t in df['Symbol'].tolist():
            tickers = tickers.append(t.replace('.', '-'))

        print(f"Success: {len(tickers)} tickers retrieved.")
        return sorted(tickers)

    except Exception as e:
        print(f"Technical error retrieving tickers: {e}")
        return []

def download_new_data(
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None
        ) -> pd.DataFrame:
    """Downloads historical price data for a specific ticker using Yahoo Finance.

    This function acts as an abstraction layer over `yfinance.download`.
    It manages date logic to avoid redundant or future downloads.
    If no dates are specified, it downloads the full available history.

    Args:
        ticker (str): The financial asset symbol (e.g., "AAPL", "MSFT").
        start_date (str | None, optional): Start date in ISO format "YYYY-MM-DD".
            If provided, the download will start from the day after this date.
        end_date (str | None, optional): End date in ISO format "YYYY-MM-DD".
            If provided, the download will include data up to this date (exclusive).

    Returns:
        pd.DataFrame: A pandas DataFrame containing historical data (Open, High, Low, Close, Volume).
            The DataFrame index is the date (DatetimeIndex).
            Returns an empty DataFrame if the start date is in the future or no data is found.
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
    
    if end_date == None:
        return yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
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
    
