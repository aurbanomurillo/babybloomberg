import yfinance as yf
import pandas as pd
import pandas as pd
import requests
from datetime import datetime, timedelta
from io import StringIO  # <--- Añade esta importación

def obtener_tickers_sp500() -> list:
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        respuesta = requests.get(url, headers=headers)
        respuesta.raise_for_status()

        # Envolvemos respuesta.text en StringIO para cumplir con la nueva norma de Pandas
        tablas = pd.read_html(StringIO(respuesta.text))
        df = tablas[0]
        # ------------------------
        
        tickers = [t.replace('.', '-') for t in df['Symbol'].tolist()]
        print(f"Éxito: {len(tickers)} tickers obtenidos.")
        return tickers

    except Exception as e:
        print(f"Error técnico al obtener tickers: {e}")
        return []


def descargar_datos_nuevos(ticker: str, start_date: str | None = None) -> pd.DataFrame:
    # print(f"Descargando datos nuevos de {ticker}...")

    if start_date == None:
        # Devuelve un dataframe con todos los datos históricos
        return yf.download( 
            ticker,
            interval="1d",
            progress=False,
            auto_adjust=True)

    start = datetime.fromisoformat(start_date) + timedelta(days=1)

    if start >= datetime.now():
        # Devuelve un dataframe vacío
        return pd.DataFrame()
    
    # Devuelve un dataframe con los datos desde start_date hasta hoy
    return yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=datetime.now().strftime("%Y-%m-%d"),
        interval="1d",
        progress=False,
        auto_adjust=True
    )
