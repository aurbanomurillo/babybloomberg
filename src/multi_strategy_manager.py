from src.exceptions import *
from src.strategy_manager import *

class MultiStrat:
    def __init__(self, strats: list):
        self.strats = strats
        self.fiat = 0
        self.profits = 0
        self.operations = []
        self.initial_capital = sum(s.initial_capital for s in self.strats)
        self.fecha_inicial = None
        self.fecha_final = None

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

    def print_performance(self):
        try:
            for operation in self.operations:
                print(operation.get_description())
            print(f"-" * 50)
            print(f"{len(self.operations)} operations executed.")
            print(f"Initial capital = {self.initial_capital / 100}$.")
            print(f"Final capital = {self.fiat / 100}$.")
            print(f"Final profit = {self.profits / 100}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
        except TradeNotClosed:
            print(f"Trade not closed.")
            
    def close_all_trades(self):
        for n in track(range(len(self.strats)), description = "Closing Trades..."):
            if not self.strats[n].closed:
                self.strats[n].close_trade(self.fecha_final)

        for n in track(range(len(self.strats)), description = "Proccessinng Profits..."):
            try:
                self.profits += self.strats[n].get_profit()
            except TradeNotClosed:
                self.strats[n].close_trade(self.fecha_final)
                self.profits+=self.strats[n].get_profit()
        
        for n in track(range(len(self.strats)), description = "Proccessinng Operations..."):
            self.fiat += self.strats[n].fiat
            self.operations += self.strats[n].operations
        
        self.operations.sort(key = lambda t: t.fecha)

    def get_returns(self) -> float:
        return round(self.profits/self.initial_capital, 8)
    
    def execute_sim(self):
        self.fecha_inicial = min(s.start for s in self.strats)
        self.fecha_final = max(s.end for s in self.strats)

        rango_fechas = get_date_range(self.fecha_inicial, self.fecha_final)

        for fecha in track(rango_fechas, description = "Processing trades..."):
            try:
                self.check_and_do_all(fecha)
            except NotEnoughStockError:
                continue

        self.close_all_trades()
