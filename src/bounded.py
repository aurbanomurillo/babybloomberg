"""Bounded trading strategy with defined limits (Stop Loss, Take Profit, and Time).

This module implements a strategy that opens a position immediately at the start
date and manages it based on strict exit rules: maximum allowable loss, target
profit, or maximum operation duration.
"""

import pandas as pd
from src.strategy import *
from src.stockframe_manager import *
from src.processing import *

class BoundedStrategy(Strategy):
    """Implements a 'buy and manage' strategy with price and time limits.

    This strategy enters the market with all available capital on the adjusted
    start date and monitors the position daily. It closes the position if a
    Stop Loss price is hit, a Take Profit price is hit, or the maximum holding
    period is exceeded.

    Attributes:
        stop_loss (float): The calculated absolute price level to cut losses.
        take_profit (float): The calculated absolute price level to take profits.
        max_holding_period (str | None): Maximum duration to hold the position
            (e.g., "30 days").
        entry_price (float): The price at which the initial entry was executed.
    """

    def __init__(
        self,
        ticker: str,
        start: str,
        end: str,
        capital: float,
        sf: StockFrame,
        stop_loss: float,
        take_profit: float,
        sl_type: str = "$",
        tp_type: str = "$",
        max_holding_period: str | None = None,
        name: str = "undefined_bounded_strategy"
        ) -> None:
        """Initializes the strategy and executes the immediate market entry.

        This method calculates the absolute Stop Loss and Take Profit levels based
        on the entry price and the specified types (percentage or absolute).
        It then executes a "Buy All" operation on the start date.

        Note:
            If the provided `start` date lacks data (e.g., it is a holiday), the
            strategy automatically advances the start date to the next available
            trading day.

        Args:
            ticker (str): The asset symbol (e.g., "AAPL").
            start (str): The desired start date (YYYY-MM-DD).
            end (str): The simulation end date (YYYY-MM-DD).
            capital (float): The initial capital available for the strategy.
            sf (StockFrame): The data manager containing price history.
            stop_loss (float): The Stop Loss value. Can be an absolute price
                difference or a percentage, depending on `sl_type`.
            take_profit (float): The Take Profit value. Can be an absolute price
                difference or a percentage, depending on `tp_type`.
            sl_type (str, optional): The type of Stop Loss calculation.
                Accepts "$" (absolute amount) or "%" (percentage). Defaults to "$".
            tp_type (str, optional): The type of Take Profit calculation.
                Accepts "$" (absolute amount) or "%" (percentage). Defaults to "$".
            max_holding_period (str | None, optional): The maximum duration to
                hold the position (e.g., "30 days"). Defaults to None.
            name (str, optional): A unique identifier for the strategy.
                Defaults to "undefined_bounded_strategy".
        """
        
        super().__init__(ticker, start, end, capital, sf, name=name)

        if not self.start in self.sf.index.tolist():
            valid_dates = self.sf.index[self.sf.index >= self.start]
            if not valid_dates.empty:
                new_start = valid_dates[0]
                self.start = new_start

        self.buy_all(self.start, trigger="initial_entry")
        self.entry_price: float = self.sf.get_price_in(self.start)

        if self.entry_price == None:
            self.entry_price = self.sf.get_last_valid_price(self.start)

        if sl_type == "%":
            self.stop_loss: float = self.entry_price * (1 + stop_loss)
        else:
            self.stop_loss: float = self.entry_price + stop_loss

        if tp_type == "%":
            self.take_profit: float = self.entry_price * (1 + take_profit)
        else:
            self.take_profit: float = self.entry_price + take_profit

        self.max_holding_period: str | None = max_holding_period

        if self.stop_loss >= self.entry_price:
            print(f"WARNING ({self.name}): Stop Loss ({round(self.stop_loss, 2)}) is >= entry price ({self.entry_price}). Position might close immediately.")
        if self.take_profit <= self.entry_price:
            print(f"WARNING ({self.name}): Take Profit ({round(self.take_profit, 2)}) is <= entry price ({self.entry_price}). Position might close immediately.")

    def check_and_do(
            self, 
            date: str
            ) -> None:
        """Evaluates exit conditions for a specific date.

        Checks against three conditions:
        1. Stop Loss: Close if current price <= stop_loss.
        2. Take Profit: Close if current price >= take_profit.
        3. Time Stop: Close if the position duration exceeds `max_holding_period`.

        Args:
            date (str): The current simulation date (YYYY-MM-DD).

        Raises:
            StopChecking: If any exit condition is met, this exception is raised
                to signal the orchestrator to stop processing further dates for
                this strategy.
        """

        super().check_and_do(date)
        current_price = self.sf.get_price_in(date)
        if not current_price == None:
            if current_price <= self.stop_loss:
                self.close_trade(date, trigger="stop_loss")
                raise StopChecking
            elif current_price >= self.take_profit:
                self.close_trade(date, trigger="take_profit")
                raise StopChecking

            elif not self.max_holding_period == None:
                cutoff_date = subtract_interval(date, self.max_holding_period)
                if cutoff_date >= self.start:
                    self.close_trade(date, trigger="time_stop")
                    raise StopChecking

    def execute(self) -> None:
        """Executes the main strategy loop over the configured date range.

        Iterates daily, verifying exit conditions via `check_and_do`. It handles
        flow control exceptions (`StopChecking`) to terminate execution early
        if the position is closed. If the position remains open at the end of
        the date range, it forces a closure.
        """

        for date in track(self.sf.index, description=f"Executing {self.name}..."):
            if self.start <= date <= self.end:
                try:
                    self.check_and_do(date)
                except NotEnoughStockError:
                    break
                except StopChecking:
                    break
        if not self.closed:
            self.close_trade(self.end)

    def execute_and_save(
            self, 
            db_route: str
            ) -> None:
        """Executes the simulation and persists daily performance metrics.

        Runs the strategy utilizing the valid trading days from `self.sf.index`.
        For each step, it triggers trading logic, calculates the current total equity
        (Cash + Stock Value), and logs the state. The resulting performance history
        is saved to the specified SQLite database.

        Args:
            db_route (str): The file path to the SQLite database.
        """

        valid_dates = [d for d in self.sf.index if self.start <= d <= self.end]
        performance_log = []

        for date in track(valid_dates, description=f"Executing and saving {self.name}..."):
            try:
                self.check_and_do(date)
            except (NotEnoughStockError, StopChecking):
                break

            total_equity = self.get_current_capital(date)
            invested_value = total_equity - self.fiat
            performance_log.append({
                "Date": date,
                "Cash": round(self.fiat, 2),
                "Stock_Value": round(invested_value, 2),
                "Total_Equity": round(total_equity, 2)
            })

        if not self.closed:
            self.close_trade(self.end)

        if len(performance_log) > 0:
            df_perf = pd.DataFrame(performance_log)
            df_perf.set_index("Date", inplace=True)
            try:
                save_to_db(str(self.name), df_perf, db_name=db_route)
                print(f"Results saved to 'performance_{self.name}'")
            except Exception as e:
                print(f"Error saving results: {e}")