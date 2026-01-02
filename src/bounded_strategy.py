from rich.progress import track
from src.strategy_manager import *
from src.stockframe_manager import *
from src.processing import *


class BoundedStrategy(Strategy):

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            stop_loss: float,
            take_profit: float,
            max_holding_period: int = None
            ):
        
        super().__init__(ticker, start, end, capital, sf)
        
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.max_holding_period = max_holding_period        
        self.buy_all(self.start, trigger="initial_entry")
        self.entry_price = self.sf.get_price_in(self.start)
        self._validar_parametros()

    def _validar_parametros(self):
        if self.stop_loss >= self.entry_price:
            print(f"ADVERTENCIA: El Stop Loss ({self.stop_loss}) es mayor que el precio de entrada ({self.entry_price}). Se venderá inmediatamente.")
        if self.take_profit <= self.entry_price:
             print(f"ADVERTENCIA: El Take Profit ({self.take_profit}) es menor que el precio de entrada ({self.entry_price}). Se venderá inmediatamente.")

    def check_and_do(
            self,
            fecha:str
            ):
        current_price = self.sf.get_price_in(fecha)
        if not current_price == None:
            if current_price <= self.stop_loss:
                self.close_trade(fecha, trigger="stop_loss")
                raise StopChecking
            elif current_price >= self.take_profit:
                self.close_trade(fecha, trigger="take_profit")
                raise StopChecking

            elif not self.max_holding_period == None:
                fecha_hace_periodo = restar_intervalo(fecha, self.max_holding_period)
                if fecha_hace_periodo >= self.start:
                    self.close_trade(fecha, trigger="time_stop")
                    raise StopChecking

    def execute(self):
        for fecha in track(self.sf.index, description="Monitoring SL/TP..."):
            if self.start <= fecha <= self.end:
                try:
                    self.check_and_do(fecha)
                except NotEnoughStockError:
                    break
                except StopChecking:
                    break
        if not self.closed:
            self.close_trade(self.end)


class DynamicBoundedStrategy(BoundedStrategy):
    """
    Estrategia que define SL y TP como porcentajes del precio de entrada.
    Ej: stop_loss_pct = -0.05 (5% pérdida), take_profit_pct = 0.10 (10% ganancia).
    """
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            stop_loss_pct: float, 
            take_profit_pct: float,
            max_holding_period: int = None
            ):
        
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

        super().__init__(
            ticker, start, end, capital, sf, 
            stop_loss=stop_loss_pct, 
            take_profit=take_profit_pct, 
            max_holding_period=max_holding_period
        )

        self.stop_loss = self.entry_price * (1 + self.stop_loss_pct)
        self.take_profit = self.entry_price * (1 + self.take_profit_pct)

    def _validar_parametros(self):
        """Validación específica para porcentajes."""
        if self.stop_loss_pct >= 0:
            print(f"⚠️ ADVERTENCIA: El Stop Loss pct ({self.stop_loss_pct}) es positivo/cero. ¿Querías decir un número negativo?")
        
        if self.take_profit_pct <= 0:
             print(f"⚠️ ADVERTENCIA: El Take Profit pct ({self.take_profit_pct}) es negativo/cero. Esto asegurará pérdidas.")