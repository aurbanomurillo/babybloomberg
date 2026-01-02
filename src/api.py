import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
from io import StringIO


def obtener_tickers_sp500() -> list[str]:
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        respuesta = requests.get(url, headers = headers)
        respuesta.raise_for_status()

        tablas = pd.read_html(StringIO(respuesta.text))
        df = tablas[0]

        tickers = []
        for t in df['Symbol'].tolist():
            tickers = tickers.append(t.replace('.', '-'))

        print(f"Éxito: {len(tickers)} tickers obtenidos.")
        return sorted(tickers)

    except Exception as e:
        print(f"Error técnico al obtener tickers: {e}")
        return []

def descargar_datos_nuevos(
        ticker: str,
        start_date: str | None = None,
        end_date: str | None = None) -> pd.DataFrame:

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
    
