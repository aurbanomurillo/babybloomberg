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
        ):
    
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

def load_stock(ticker:str, ):
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


def load_stocks(lista_tickers):
    for ticker in track(lista_tickers, description = "Procesando..."):
        load_stock(ticker)
    
def get_primera_fecha(
        ticker: str | StockFrame,
        ruta_db: str = 'data/bolsa.db'
        ) -> str | None:
    try:
        if isinstance(ticker, str):
            df = get_sf_from_sqlite(ticker, ruta_db)

            return df.index[0]
        elif isinstance(ticker, StockFrame):
            return ticker.index[0]

    except (pd.errors.DatabaseError, sqlite3.OperationalError) as e:
        return None

def get_ultima_fecha(
        ticker: str,
        ruta_db: str = 'data/bolsa.db'
        ) -> str | None:
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