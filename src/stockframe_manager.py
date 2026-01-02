import pandas as pd
from datetime import datetime, timedelta

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
    
    def get_last_valid_price(
            self,
            target_date_str: str) -> float | None:
        
        first_available_date = self.index[0] 
        current_date_str = target_date_str
        
        while current_date_str >= first_available_date:
            
            price = self.get_price_in(current_date_str)
            
            if not price == None:
                return price
            
            current_date_dt = datetime.strptime(current_date_str, "%Y-%m-%d")
            previous_date_dt = current_date_dt - timedelta(days=1)
            current_date_str = previous_date_dt.strftime("%Y-%m-%d")

        return None