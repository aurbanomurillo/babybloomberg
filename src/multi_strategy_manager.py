from rich.progress import track
from src.processing import *
from src.exceptions import *
from src.strategy_manager import *

class MultiStrat(Strategy):
    def __init__(
            self,
            strats: list[Strategy],
            ):
        self.strats = strats
        self.start = min(s.start for s in self.strats)
        self.end = max(s.end for s in self.strats)
        self.fiat = 0
        self.profits = 0
        self.operations = []
        self.initial_capital = sum(s.initial_capital for s in self.strats)


    def check_and_do_all(self, fecha):
        for n in range(len(self.strats)):
            try:
                self.strats[n].check_and_do(fecha)
            except StopChecking:
                try:
                    self.strats[n].close_trade(fecha)
                except Exception:
                    pass
            except NotEnoughStockError:
                continue
            
    def close_all_trades(self):
        for n in track(range(len(self.strats)), description = "Closing Trades..."):
            if not self.strats[n].closed:
                self.strats[n].close_trade(self.fecha_final)

        for n in track(range(len(self.strats)), description = "Proccessinng Profits..."):
            try:
                self.profits += self.strats[n].get_profit()
            except TradeNotClosed:
                self.strats[n].close_trade(self.end)
                self.profits+=self.strats[n].get_profit()
        
        for n in track(range(len(self.strats)), description = "Proccessinng Operations..."):
            self.fiat += self.strats[n].fiat
            self.operations += self.strats[n].operations
        
        self.operations.sort(key = lambda t: t.fecha)
    
    def execute_sim(self):
        rango_fechas = get_date_range(self.start, self.end)

        for fecha in track(rango_fechas, description = "Processing trades..."):
            try:
                self.check_and_do_all(fecha)
            except NotEnoughStockError:
                continue

        self.close_all_trades()
