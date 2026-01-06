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

        self.active_strategies: list[Strategy] = strats
        self.finished_strategies: list[Strategy] = []
        
        self.start: str = min(s.start for s in self.active_strategies)
        self.end: str = max(s.end for s in self.active_strategies)
        
        self.fiat: float = 0.0 
        self.initial_capital: float = sum(s.initial_capital for s in self.active_strategies)
        
        self.profits: float = 0.0
        self.closed: bool = False
        self.name: str = "undefined_multi_strategy"

    def check_and_do(
            self, 
            date: str
            ) -> None:
        """Delegates the daily check to each active sub-strategy.

        Iterates through all `active_strategies`. If a sub-strategy finishes
        (raises `StopChecking` or similar exceptions) or runs out of resources,
        it is moved to `finished_strategies`, and its remaining liquid capital
        is added to the global fiat pool.

        Args:
            date (str): Current date to evaluate.
        """

        for strat in self.active_strategies[:]:
            try:
                strat.check_and_do(date)
            except (StopChecking, NotEnoughStockError, NotEnoughCashError):
                if not strat.closed:
                    try:
                        strat.close_trade(date, trigger="sub_strategy_finish")
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

        date_range = get_date_range(self.start, self.end)

        for date in track(date_range, description=f"Executing {self.name}..."):
            self.check_and_do(date)

        self.close_trade(self.end)

    def execute_and_save(
            self,
            db_route: str = "strategy_data.db"
            ) -> None:
        """Executes the multi-strategy simulation and persists daily performance metrics.

        Runs the strategy manager day-by-day over the configured date range. It triggers
        the daily logic for all active sub-strategies, aggregates their combined 
        financial state (Cash + Stock Value), and logs the consolidated performance.

        Finally, the performance history is saved to the specified database.

        Args:
            db_route (str, optional): The file path to the SQLite database where the 
                performance table (named after the strategy) will be saved. 
                Defaults to "strategy_data.db".
        """
        
        date_range = get_date_range(self.start, self.end)
        
        performance_log = []

        for date in track(date_range, description=f"Executing and saving {self.name}..."):
            
            self.check_and_do(date)
            
            total_equity = self.get_current_capital(date)
            
            invested_value = total_equity - self.fiat
            
            performance_log.append({
                "Date": date,
                "Cash": round(self.fiat, 2),
                "Stock_Value": round(invested_value, 2),
                "Total_Equity": round(total_equity, 2)
            })

        self.close_trade(self.end)
        
        if performance_log:
            df_perf = pd.DataFrame(performance_log)
            
            df_perf.set_index("Date", inplace=True)
            
            table_name = str(self.name)
            
            try:
                save_to_db(table_name, df_perf, db_name=db_route)
                print(f"Saved data in '{table_name}' from {db_route}")
            except Exception as e:
                print(f"Error saving results: {e}")

    def close_trade(
            self,
            date: str,
            trigger: str = "force_close_global"
            ) -> None:
        """Forces the closure of all remaining active sub-strategies.

        Called at the end of the simulation. Triggers the `close_trade` method
        of every active strategy, aggregates the final capital, and calculates
        the total profit.

        Args:
            date (str): Date of closure.
            trigger (str, optional): Reason for closure. Defaults to "force_close_global".
        """

        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(date, trigger=trigger)
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
        
        all_operations.sort(key=lambda x: x.date)
        return [op.get_description() for op in all_operations]

    def print_operations(self) -> None:
        """Prints a consolidated log of all operations across the sub-strategies."""

        print(f"--- Operations Detail for {self.name} ({len(self.finished_strategies) + len(self.active_strategies)} sub-strategies) ---")
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
        
    def get_current_capital(
            self, 
            date: str
            ) -> float:
        """Calculates the total consolidated equity of the multi-strategy.

        Aggregates the current value by summing the unallocated cash (fiat) held
        by the manager and the total current capital (equity) of all currently 
        active sub-strategies.

        Args:
            date (str): Date to evaluate (YYYY-MM-DD).

        Returns:
            float: Total consolidated portfolio value rounded to 2 decimal places.
        """

        active_capital = 0
        for strat in self.active_strategies:
            active_capital += strat.get_current_capital(date)
        
        return round(self.fiat + active_capital, 2)
        