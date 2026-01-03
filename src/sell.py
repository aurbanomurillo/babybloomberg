from src.strategy import *
from src.stockframe_manager import *

class SellStrategy(Strategy):
    
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade:float,
            threshold:tuple[float, float] | float,
            sizing_type:str = "static",
            name:str = "undefined_static_sell_strategy"
            ):
        
        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        self.threshold:str = threshold
        self.amount_per_trade:float = amount_per_trade
        self.buy_all(self.start, trigger="initial_restock")


    def check_and_do(
            self,
            fecha:str
            ) -> None:
        precio_actual = self.sf.get_price_in(fecha)
        if type(self.threshold) == tuple:
            if self.start <= fecha < self.end and not precio_actual == None and self.threshold[0] <= precio_actual <= self.threshold[1]:
                self.sell(self.amount_per_trade, fecha, trigger="automatic_check")
        elif type(self.threshold) == float:
            if self.start <= fecha < self.end and not precio_actual == None and precio_actual == self.threshold:
                self.sell(self.amount_per_trade, fecha, trigger="automatic_check")
        if fecha >= self.end:
            raise StopChecking

    def execute(self) -> None:
        for fecha in track(self.sf.index, description = f"Executing {self.name}..."):
            try:
                self.check_and_do(fecha)
            except NotEnoughStockError:
                self.close_trade(fecha)
                break
            except StopChecking:
                break

        self.close_trade(self.end)

class DynamicSellStrategy(SellStrategy):
    
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade:float,
            threshold:tuple[float, float] | float,
            trigger_lookback:str = "1 day",
            sizing_type:str = "static",
            name:str = "undefined_dynamic_sell_strategy"
            ):
        
        if isinstance(threshold, float):
            if threshold <= -1:
                raise NotValidIntervalError("El threshold no puede ser -100% o menor.")
        elif isinstance(threshold, tuple):
            if threshold[0] <= -1 or threshold[1] <= -1:
                raise NotValidIntervalError("Ningún límite del rango puede ser -100% o menor.")
            
        super().__init__(
            ticker, start, end, capital, sf, 
            amount_per_trade, 
            threshold,
            sizing_type = sizing_type,
            name = name
            )
            
        self.trigger_lookback = trigger_lookback

    def check_and_do(
            self,
            fecha:str
            ) -> None:
        precio_actual = self.sf.get_price_in(fecha)
        precio_a_comparar = self.sf.get_last_valid_price(restar_intervalo(fecha,self.trigger_lookback))

        if (self.start <= fecha < self.end and
                not precio_actual == None and
                not precio_a_comparar == None
                ):
            if isinstance(self.threshold,float):
                if self.threshold > 0:
                    if precio_actual >= (1 + self.threshold) * precio_a_comparar:
                        self.sell(self.amount_per_trade, fecha, trigger="dynamic_check")
                        
                elif self.threshold < 0:
                    if precio_actual <= (1 + self.threshold) * precio_a_comparar:
                        self.sell(self.amount_per_trade, fecha, trigger="dynamic_check")
            elif isinstance(self.threshold,tuple):
                rango_precios = sorted([(1+self.threshold[0])*precio_a_comparar,(1+self.threshold[1])*precio_a_comparar])
                if rango_precios[0] <= precio_actual <= rango_precios[1]:
                    self.sell(self.amount_per_trade, fecha, trigger="dynamic_check")

        if fecha >= self.end:
            raise StopChecking