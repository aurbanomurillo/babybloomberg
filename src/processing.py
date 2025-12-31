import pandas as pd
from datetime import datetime, timedelta


class StockFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return StockFrame

    def get_price_in(self, fecha: str)->int:
        try:
            return self.loc[fecha]['Close']
        except KeyError:
            # print(f"Error: La fecha {fecha} no existe en los datos.")
            return None
        
def redondear_precio(datos: pd.DataFrame) -> pd.DataFrame:
    if datos.empty:
        return datos

    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    
    datos.index.name = "Fecha" 
    
    columnas_precio = ['Open', 'High', 'Low', 'Close', 'Adj Close']
    for col in columnas_precio:
        if col in datos.columns:
            datos[col] = (datos[col] * 100).astype(int)
    
    datos.index = datos.index.astype(str)
    return datos

def get_price_in(df, fecha:str)->int:
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
