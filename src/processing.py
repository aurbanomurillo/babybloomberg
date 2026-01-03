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

def redondear_precio(datos: pd.DataFrame) -> pd.DataFrame | StockFrame:
    """Rounds financial data columns to two decimal places.

    Standardizes the format of the DataFrame by ensuring the index is named "Fecha"
    and rounding typical price columns (Open, High, Low, Close, Adj Close).
    Handles potential MultiIndex structures returned by some data sources.

    Args:
        datos (pd.DataFrame | StockFrame): Raw data containing price history.

    Returns:
        pd.DataFrame | StockFrame: The processed DataFrame with rounded float values.
            Returns the original object if it is empty.
    """

    if datos.empty:
        return datos

    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    
    datos.index.name = "Fecha" 
    columnas_precio = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    
    for col in columnas_precio:
        if col in datos.columns:
            datos[col] = datos[col].astype(float).round(2)
    
    datos.index = datos.index.astype(str)
    return datos

def get_price_in(
        df: StockFrame | pd.DataFrame,
        fecha:str
        ) -> float:
    """Retrieves the closing price for a specific date.

    A helper function to safely extract the 'Close' value from the data source.

    Args:
        df (StockFrame | pd.DataFrame): The data source.
        fecha (str): The date to query (YYYY-MM-DD).

    Returns:
        float: The closing price on the specified date.
    """

    return float(df.loc[fecha]['Close'])

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
    
    lista_fechas = []
    current = start
    
    while current <= end:
        lista_fechas.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
        
    return lista_fechas

def restar_intervalo(
        fecha_str:str,
        intervalo_str:str
        ) -> str:
    """Subtracts a natural language time interval from a given date.

    Parses strings like "1 day", "2 weeks", "3 months" and calculates the
    resulting past date.

    Args:
        fecha_str (str): The reference date (YYYY-MM-DD).
        intervalo_str (str): The interval to subtract (e.g., "5 days", "1 year").

    Returns:
        str: The resulting past date in "YYYY-MM-DD" format.

    Raises:
        NotValidIntervalError: If the unit (day, week, month, year) is not recognized.
    """
    
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    
    partes = intervalo_str.split()
    cantidad = int(partes[0])
    unidad = partes[1].lower()
    if 'd' in unidad:
        delta = relativedelta(days=cantidad)
    elif 'w' in unidad:
        delta = relativedelta(weeks=cantidad)
    elif  'm' in unidad:
        delta = relativedelta(months=cantidad)
    elif 'y' in unidad:
        delta = relativedelta(years=cantidad)
    else:
        raise NotValidIntervalError("Unidad no reconocida (usa day, week, month, year)")

    nueva_fecha = fecha_dt - delta

    return nueva_fecha.strftime("%Y-%m-%d")
