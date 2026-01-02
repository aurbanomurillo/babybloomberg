import pandas as pd

class StockFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return StockFrame

    def get_price_in(self, fecha: str) -> float:
        try:
            return float(self.loc[fecha]['Close'])
        except KeyError:
            # print(f"Error: La fecha {fecha} no existe en los datos.")
            return None