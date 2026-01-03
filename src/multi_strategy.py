from rich.progress import track
from src.processing import *
from src.exceptions import *
from src.strategy import *

class MultiStrategy(Strategy):
    
    def __init__(
            self,
            strats: list[Strategy],
            ):
        
        self.active_strategies = strats
        self.finished_strategies = []
        
        self.start = min(s.start for s in self.active_strategies)
        self.end = max(s.end for s in self.active_strategies)
        
        self.fiat = 0 
        self.initial_capital = sum(s.initial_capital for s in self.active_strategies)
        
        self.profits = 0
        self.closed = False

    def check_and_do(
            self, 
            fecha:str
            ):
        for strat in self.active_strategies[:]:
            try:
                strat.check_and_do(fecha)
            except (StopChecking, NotEnoughStockError):
                if not strat.closed:
                    try:
                        strat.close_trade(fecha, trigger="sub_strategy_finish")
                    except:
                        pass
        
                self.fiat += strat.fiat
                
                self.finished_strategies.append(strat)
                self.active_strategies.remove(strat)

    def execute(self):
        rango_fechas = get_date_range(self.start, self.end)

        for fecha in track(rango_fechas, description="Running Multi-Strategy..."):
            self.check_and_do(fecha)

        self.close_trade(self.end)
            
    def close_trade(
            self,
            fecha:str,
            trigger:str="force_close_global"
            ):
        
        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(fecha, trigger=trigger)
                self.fiat += strat.fiat
                self.finished_strategies.append(strat)
        
        self.active_strategies = []
        
        self.profits = round(self.fiat - self.initial_capital, 2)
        self.closed = True

    def get_all_operations(self) -> list[str]:
        all_strats = self.active_strategies + self.finished_strategies
        all_operations:list[Operation] = []
        for strat in all_strats:
            all_operations.extend(strat.operations)
        
        all_operations.sort(key=lambda x: x.fecha)
        return [op.get_description() for op in all_operations]

    def print_operations(self):
        print(f"--- Detalle de Operaciones ({len(self.finished_strategies) + len(self.active_strategies)} sub-estrategias) ---")
        for description in self.get_all_operations():
            print(description)

    def print_performance(self):
        all_strats = self.active_strategies + self.finished_strategies
        total_operations = sum(len(strat.operations) for strat in all_strats)

        try:
            print(f"-" * 50)
            print(f"{total_operations} operations executed across {len(all_strats)} sub-strategies.")
            print(f"Initial capital = {round(self.initial_capital, 2)}$.")
            print(f"Final capital = {round(self.fiat, 2)}$.")
            print(f"Final profit = {round(self.get_profit(), 2)}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
            print(f"-" * 50)
        except TradeNotClosed:
            print(f"Trade not closed.")

    def get_profit(self) -> float:
        if self.closed:
            return self.profits
        else:
            raise TradeNotClosed
        