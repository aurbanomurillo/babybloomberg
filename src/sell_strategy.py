from src.strategy_manager import *
from src.stockframe_manager import *

class SellStrat(Strategy):
    
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade:float,
            threshold:tuple[float, float] | float
            ):
        
        super().__init__(ticker, start, end, capital, sf)
        self.threshold = threshold
        self.amount_per_trade = amount_per_trade
        self.buy_all(self.start)

    def check_and_do(
            self,
            fecha:str
            ):
        precio_actual = self.sf.get_price_in(fecha)
        if type(self.threshold) == tuple:
            if self.start <= fecha < self.end and not precio_actual == None and self.threshold[0] <= precio_actual <= self.threshold[1]:
                self.sell(self.amount_per_trade, fecha)
        elif type(self.threshold) == float:
            if self.start <= fecha < self.end and not precio_actual == None and precio_actual == self.threshold:
                self.sell(self.amount_per_trade, fecha)
        if fecha >= self.end:
            raise StopChecking

    def execute(self):
        for fecha in track(self.sf.index, description = "Processing trades..."):
            try:
                self.check_and_do(fecha)
            except NotEnoughStockError:
                break
            except StopChecking:
                break

        self.close_trade(self.end)
