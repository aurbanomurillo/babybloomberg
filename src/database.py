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

def guardar_en_db(
        nombre_tabla: str,
        df: pd.DataFrame,
        db_name: str = 'data/bolsa.db'
        ) -> None:
    """Persists a DataFrame into a specific table in the SQLite database.

    Creates the table if it does not exist, defining columns dynamically based on the DataFrame.
    Data is inserted in bulk to optimize performance.

    Args:
        nombre_tabla (str): Table name (usually the asset ticker).
        df (pd.DataFrame): Data to save. The index will be reset to save it as a column.
        db_name (str, optional): Path to the .db file. Defaults to 'data/bolsa.db'.
    """

    with sqlite3.connect(db_name) as conexion:
        cursor = conexion.cursor()

        df_guardar = df.reset_index()

        columnas = list(df_guardar.columns)
        definicion = ", ".join(
            [f"[{col}] TEXT" for col in columnas]
        )

        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS [{nombre_tabla}] ({definicion})"
        )

        placeholders = ", ".join(["?" for _ in range(len(columnas))])
        cursor.executemany(
            f"INSERT INTO [{nombre_tabla}] VALUES ({placeholders})",
            df_guardar.values.tolist()
        )

        conexion.commit()

def load_stock(ticker:str) -> None:
    """Updates or downloads the full history of a specific asset.

    Checks the last available date in the local database for that ticker.
    If data exists, it downloads only the differential (delta) since the last date.
    If not, it downloads the full history. New data is cleaned and saved.

    Args:
        ticker (str): Symbol of the asset to update (e.g., "AAPL").
    """

    if not os.path.exists('data/bolsa.db'):
        print("Archivo de datos inexistente. Se procederá a crear uno.")
    try:
        ultima_fecha = get_ultima_fecha(ticker)
        datos = descargar_datos_nuevos(ticker, ultima_fecha)

        if datos.empty:
            # print(f"{ticker}: ya actualizado")
            return None

        datos_limpios = redondear_precio(datos)
        guardar_en_db(ticker, datos_limpios)

        # print(f"{ticker}: actualizado desde {datos_limpios['Fecha'].iloc[0]} hasta {datos_limpios['Fecha'].iloc[-1]}")
    except Exception as e:
        print(f"Falló {ticker}: {e}")

def load_stocks(lista_tickers: list[str]) -> None:
    """Executes bulk loading and updating for a list of assets.

    Iterates over the provided list invoking `load_stock` for each element.
    Displays a visual progress bar in the console.

    Args:
        lista_tickers (list[str]): List of symbols to process.
    """

    for ticker in track(lista_tickers, description = "Almacenando datos..."):
        load_stock(ticker)
    
def get_primera_fecha(
        ticker: str | StockFrame,
        ruta_db: str = 'data/bolsa.db'
        ) -> str | None:
    """Retrieves the earliest available date for an asset.

    Can query the database directly (if a ticker string is passed)
    or inspect a StockFrame object already loaded in memory.

    Args:
        ticker (str | StockFrame): Asset symbol or data object.
        ruta_db (str, optional): Path to the database (only if ticker is str).

    Returns:
        str | None: Date in "YYYY-MM-DD" format or None if no data exists or connection fails.
    """
    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, ruta_db)

            return df.index[0]
        elif isinstance(ticker, StockFrame):
            return ticker.index[0]

    except (pd.errors.DatabaseError, sqlite3.OperationalError) as e:
        return None

def get_ultima_fecha(
        ticker: str | StockFrame,
        ruta_db: str = 'data/bolsa.db'
        ) -> str | None:
    """Retrieves the most recent available date for an asset.

    Useful for determining from which point new data should be downloaded.
    Works by both querying SQL and inspecting an in-memory StockFrame.

    Args:
        ticker (str | StockFrame): Asset symbol or data object.
        ruta_db (str, optional): Path to the database.

    Returns:
        str | None: Date in "YYYY-MM-DD" format or None if no data exists or connection fails.
    """
    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, ruta_db)

            return df.index[-1]
        elif isinstance(ticker, StockFrame):
            return ticker.index[-1]


    except (pd.errors.DatabaseError, sqlite3.OperationalError): 
        return None

def get_sf_from_sqlite(
        ticker: str,
        ruta_db: str = 'data/bolsa.db',
        start: str | None = None,
        end: str | None = None
        ) -> StockFrame:
    """Retrieves asset data from the database and constructs a StockFrame.

    Reads the table corresponding to the ticker, removes duplicates by date, and ensures
    that numeric columns (Open, High, Low, Close, Adj Close) have the correct type.
    Allows filtering by date range optionally.

    Args:
        ticker (str): Symbol of the table/asset to read.
        ruta_db (str, optional): Path to the database.
        start (str | None, optional): Filter start date (inclusive).
        end (str | None, optional): Filter end date (inclusive).

    Returns:
        StockFrame: Object with clean historical data indexed by date.
    """

    with sqlite3.connect(ruta_db) as conexion:
        query = f"""
            SELECT * 
            FROM 
            {ticker}"""        
        df = pd.read_sql_query(query, conexion)
    
    if 'Fecha' in df.columns:
        df = df.drop_duplicates(subset=['Fecha'], keep='last')
        df.set_index('Fecha', inplace=True)
        
        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]
       
    cols_to_fix = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
            
    return StockFrame(df)
