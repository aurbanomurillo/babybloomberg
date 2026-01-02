import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from src.exceptions import *

def redondear_precio(datos: pd.DataFrame) -> pd.DataFrame:
    if datos.empty:
        return datos

    # Aplanar MultiIndex si existe (común en nuevas versiones de yfinance)
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    
    datos.index.name = "Fecha" 
    
    # Lista de posibles columnas de precio
    columnas_precio = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    
    for col in columnas_precio:
        # IMPORTANTE: Verificamos si la columna existe antes de tocarla
        if col in datos.columns:
            datos[col] = datos[col].astype(float).round(2)
    
    datos.index = datos.index.astype(str)
    return datos

def get_price_in(df, fecha:str) -> float:
    return df.loc[fecha]['Close']

def get_date_range(start_str: str, end_str: str) -> list[str]:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    
    lista_fechas = []
    current = start
    
    while current <= end:
        lista_fechas.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
        
    return lista_fechas

def restar_intervalo(fecha_str:str, intervalo_str:str) -> str:
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
