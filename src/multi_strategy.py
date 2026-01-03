"""
Orchestrator for concurrent execution of multiple trading strategies.

This module defines a container class that manages and executes a collection
of different strategy instances simultaneously. It aggregates their capital,
operations, and performance metrics into a single global result.
"""

from src.processing import *
from src.exceptions import *
from src.strategy import *

class MultiStrategy(Strategy):
    """A container strategy that executes multiple sub-strategies in parallel.

    Acts as a wrapper that iterates through a list of provided strategy instances,
    triggering their daily checks and managing their lifecycle. It automatically
    determines the global start and end dates based on the sub-strategies.

    Attributes:
        active_strategies (list[Strategy]): List of currently running strategies.
        finished_strategies (list[Strategy]): List of completed strategies.
        fiat (float): Aggregated available cash (cleared from finished strategies).
    """

    def __init__(
            self,
            strats: list[Strategy],
            ):
        """Initializes the multi-strategy manager.

        Calculates the global simulation period (earliest start date to latest end date)
        and sums the initial capital from all provided strategies.

        Args:
            strats (list[Strategy]): A list of initialized strategy objects to be executed.
        """

        self.active_strategies:list[Strategy] = strats
        self.finished_strategies:list[Strategy] = []
        
        self.start:str = min(s.start for s in self.active_strategies)
        self.end:str = max(s.end for s in self.active_strategies)
        
        self.fiat:float = 0.0 
        self.initial_capital:float = sum(s.initial_capital for s in self.active_strategies)
        
        self.profits:float = 0.0
        self.closed:bool = False
        self.name:str = "undefined_multi_strategy"

    def check_and_do(
            self, 
            fecha:str
            ) -> None:
        """Delegates the daily check to each active sub-strategy.

        Iterates through all `active_strategies`. If a sub-strategy finishes
        (raises `StopChecking` or similar exceptions) or runs out of resources,
        it is moved to `finished_strategies`, and its remaining liquid capital
        is added to the global fiat pool.

        Args:
            fecha (str): Current date to evaluate.
        """

        for strat in self.active_strategies[:]:
            try:
                strat.check_and_do(fecha)
            except (StopChecking, NotEnoughStockError, NotEnoughCashError):
                if not strat.closed:
                    try:
                        strat.close_trade(fecha, trigger="sub_strategy_finish")
                    except:
                        pass
        
                self.fiat += strat.fiat
                
                self.finished_strategies.append(strat)
                self.active_strategies.remove(strat)

    def execute(self) -> None:
        """Runs the combined simulation over the calculated global date range.

        Generates the full range of dates from the earliest start to the latest end
        and iterates day-by-day calling `check_and_do`.
        """

        rango_fechas = get_date_range(self.start, self.end)

        for fecha in track(rango_fechas, description=f"Executing {self.name}..."):
            self.check_and_do(fecha)

        self.close_trade(self.end)
            
    def close_trade(
            self,
            fecha:str,
            trigger:str="force_close_global"
            ) -> None:
        """Forces the closure of all remaining active sub-strategies.

        Called at the end of the simulation. Triggers the `close_trade` method
        of every active strategy, aggregates the final capital, and calculates
        the total profit.

        Args:
            fecha (str): Date of closure.
            trigger (str, optional): Reason for closure. Defaults to "force_close_global".
        """

        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(fecha, trigger=trigger)
                self.fiat += strat.fiat
                self.finished_strategies.append(strat)
        
        self.active_strategies = []
        
        self.profits = round(self.fiat - self.initial_capital, 2)
        self.closed = True

    def get_all_operations(self) -> list[str]:
        """Aggregates and sorts operations from all sub-strategies.

        Returns:
            list[str]: A chronological list of descriptions for every buy/sell operation
                performed by any of the managed strategies.
        """

        all_strats = self.active_strategies + self.finished_strategies
        all_operations:list[Operation] = []
        for strat in all_strats:
            all_operations.extend(strat.operations)
        
        all_operations.sort(key=lambda x: x.fecha)
        return [op.get_description() for op in all_operations]

    def print_operations(self) -> None:
        """Prints a consolidated log of all operations across the sub-strategies."""

        print(f"--- Detalle de Operaciones {self.name} ({len(self.finished_strategies) + len(self.active_strategies)} sub-estrategias) ---")
        for description in self.get_all_operations():
            print(description)

    def print_performance(self) -> None:
        """Prints a summary of the global performance, aggregating capital and profits."""

        all_strats = self.active_strategies + self.finished_strategies
        total_operations = sum(len(strat.operations) for strat in all_strats)

        try:
            print(f"-" * 50)
            print(f" --- Performance of {self.name} ---")
            print(f"{total_operations} operations executed across {len(all_strats)} sub-strategies.")
            print(f"Initial capital = {round(self.initial_capital, 2)}$.")
            print(f"Final capital = {round(self.fiat, 2)}$.")
            print(f"Final profit = {round(self.get_profit(), 2)}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
            print(f"-" * 50)
        except TradeNotClosed:
            print(f"Trade not closed.")

    def get_profit(self) -> float:
        """Retrieves the total profit generated by the multi-strategy.

        Returns:
            float: The difference between the final aggregated capital and the initial capital.

        Raises:
            TradeNotClosed: If the strategy is still running (has not been closed).
        """
        
        if self.closed:
            return self.profits
        else:
            raise TradeNotClosed
        