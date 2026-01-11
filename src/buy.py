"""Buy (Long) strategies based on price levels or relative movements.

This module defines strategies specialized in opening long positions.
It includes a static variant (`BuyStrategy`) that operates on fixed absolute prices
or target ranges, and a dynamic variant (`DynamicBuyStrategy`) that operates on
percentage variations (dips or breakouts) relative to a historical timeframe.
"""

from src.strategy import *
from src.stockframe_manager import *
from typing import Tuple, Union

class BuyStrategy(Strategy):
    """Implements a static buy strategy based on absolute price levels.

    This strategy executes buy orders when the asset price reaches a specific
    target value or enters a pre-determined price range. It manages liquidity
    by attempting to buy the defined amount; if insufficient capital exists,
    it handles the exception within the execution loop.

    Attributes:
        threshold (float | tuple[float, float]): The target price (if float) or
            the inclusive price range (min, max) to trigger a buy.
        amount_per_trade (float): The amount of capital to invest in each
            operation.
    """

    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            amount_per_trade: float,
            threshold: Union[Tuple[float, float], float],
            sizing_type: str = "static",
            name: str = "undefined_static_buy_strategy"
            ) -> None:
        """Initializes the static buy strategy with a fixed price target.

        Args:
            ticker (str): The asset symbol (e.g., "AAPL").
            start (str): The simulation start date (YYYY-MM-DD).
            end (str): The simulation end date (YYYY-MM-DD).
            capital (float): The initial capital available for the strategy.
            sf (StockFrame): The data manager containing price history.
            amount_per_trade (float): The monetary amount to invest per buy signal.
            threshold (Union[Tuple[float, float], float]): The price trigger.
                - If float: The exact price at which the buy will be triggered.
                - If tuple: An inclusive range (min, max) within which the buy
                  will be triggered.
            sizing_type (str, optional): The method for position sizing (e.g.,
                "static", "percentage"). Defaults to "static".
            name (str, optional): A unique identifier for the strategy.
                Defaults to "undefined_static_buy_strategy".
        """
        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        self.threshold: Union[Tuple[float, float], float] = threshold
        self.amount_per_trade: float = amount_per_trade

    def check_and_do(
            self,
            date: str
            ) -> None:
        """Evaluates market conditions against the configured static threshold.

        Compares the asset's price on the given date with the `threshold`.
        - If `threshold` is a tuple, checks if the price is within [min, max].
        - If `threshold` is a float, checks for strict equality with the price.

        If the condition is met, a buy order is executed.

        Args:
            date (str): The current simulation date (YYYY-MM-DD).

        Raises:
            StopChecking: If the current date has reached or exceeded the
                strategy's end date, signaling the loop to terminate.
        """
        super().check_and_do(date)
        current_price = self.sf.get_price_in(date)
        
        if isinstance(self.threshold, tuple):
            if (self.start <= date < self.end and 
                current_price is not None and 
                self.threshold[0] <= current_price <= self.threshold[1]):
                self.buy(self.amount_per_trade, date, trigger="automatic_check")
                
        elif isinstance(self.threshold, float):
            if (self.start <= date < self.end and 
                current_price is not None and 
                current_price == self.threshold):
                self.buy(self.amount_per_trade, date, trigger="automatic_check")
                
        if date >= self.end:
            raise StopChecking
    
    def execute(self) -> None:
        """Executes the main strategy simulation loop.

        Iterates through the date range defined in the StockFrame. It handles
        liquidity shortages (`NotEnoughCashError`) by attempting a final
        "Buy All" operation before terminating. It ensures any open position
        is closed upon reaching the simulation end date.
        """
        for date in track(self.sf.index, description=f"Executing {self.name}..."):
            try:
                self.check_and_do(date)
            except NotEnoughCashError:
                self.buy_all(date, trigger="last_automatic_check")
                break
            except StopChecking:
                break

        self.close_trade(self.end)
    
    def execute_and_save(
            self, 
            db_route: str
            ) -> None:
        """Executes the simulation and persists daily performance metrics.

        Runs the strategy day-by-day using valid trading days from `self.sf.index`.
        It specifically handles `NotEnoughCashError` by triggering a final `buy_all`
        operation to invest remaining capital. It calculates daily equity
        (Cash + Stock Value) and saves the consolidated performance history to a
        SQLite database.

        Args:
            db_route (str): The file path to the SQLite database where the
                performance table will be saved.
        """
        valid_dates = [d for d in self.sf.index if self.start <= d <= self.end]
        performance_log = []

        for date in track(valid_dates, description=f"Executing and saving {self.name}..."):
            try:
                self.check_and_do(date)
            except NotEnoughCashError:
                self.buy_all(date, trigger="last_automatic_check")
                break
            except StopChecking:
                break
            except Exception as e:
                print(f"Error in {self.name} ({date}): {e}")
                break

            total_equity = self.get_current_capital(date)
            invested_value = total_equity - self.fiat
            performance_log.append({
                "Date": date,
                "Cash": round(self.fiat, 2),
                "Stock_Value": round(invested_value, 2),
                "Total_Equity": round(total_equity, 2)
            })

        self.close_trade(self.end)
        
        if len(performance_log) > 0:
            df_perf = pd.DataFrame(performance_log)
            df_perf.set_index("Date", inplace=True)
            try:
                save_to_db(f"performance_{self.name}", df_perf, db_name=db_route)
                print(f"Results saved to 'performance_{self.name}'")
            except Exception as e:
                print(f"Error saving results: {e}")            

class DynamicBuyStrategy(BuyStrategy):
    """Implements a dynamic buy strategy based on relative percentage variations.

    Unlike the static strategy, this class triggers buy orders by comparing the
    current price with a historical reference price (`trigger_lookback`). It
    supports two main behaviors:
    1. Momentum/Breakout: Buying when price increases by X% (positive threshold).
    2. Mean Reversion/Dip: Buying when price drops by X% (negative threshold).

    Attributes:
        trigger_lookback (str): The time interval used to determine the historical
            reference price (e.g., "1 day", "1 week").
    """

    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            amount_per_trade: float,
            threshold: Union[Tuple[float, float], float],
            trigger_lookback: str = "1 day",
            sizing_type: str = "static",
            name: str = "undefined_dynamic_buy_strategy"
            ) -> None:
        """Initializes the dynamic strategy and validates thresholds.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Capital to invest per trade.
            threshold (Union[Tuple[float, float], float]): The percentage variation trigger.
                - Float > 0: Buy on breakout (e.g., 0.10 for +10%).
                - Float < 0: Buy on dip (e.g., -0.05 for -5%).
                - Tuple: Buy if the relative change falls within the range.
            trigger_lookback (str, optional): The lookback period string.
                Defaults to "1 day".
            sizing_type (str, optional): Position sizing method. Defaults to "static".
            name (str, optional): Strategy name.

        Raises:
            NotValidIntervalError: If any threshold value implies a drop of 100%
                or more (<= -1.0), which is invalid for asset prices.
        """
        if isinstance(threshold, float):
            if threshold <= -1:
                raise NotValidIntervalError("Threshold cannot be -100% or lower.")
        elif isinstance(threshold, tuple):
            if threshold[0] <= -1 or threshold[1] <= -1:
                raise NotValidIntervalError("No range limit can be -100% or lower.")
        
        super().__init__(
            ticker, start, end, capital, sf, 
            amount_per_trade, 
            threshold,
            sizing_type = sizing_type,
            name = name
            )
        self.trigger_lookback: str = trigger_lookback

    def check_and_do(
            self,
            date: str
            ) -> None:
        """Evaluates price variation relative to the historical lookback period.

        Calculates a reference price from `trigger_lookback` ago.
        - If `threshold` > 0: Buys if current price >= reference * (1 + threshold).
        - If `threshold` < 0: Buys if current price <= reference * (1 + threshold).
        - If `threshold` is a tuple: Buys if the theoretical target price falls
          within the calculated range.

        Args:
            date (str): The current simulation date (YYYY-MM-DD).

        Raises:
            StopChecking: If the simulation end date is reached.
        """
        current_price = self.sf.get_price_in(date)
        reference_price = self.sf.get_last_valid_price(subtract_interval(date, self.trigger_lookback))

        if (self.start <= date < self.end and
                current_price is not None and
                reference_price is not None
                ):
            if isinstance(self.threshold, float):
                if self.threshold > 0:
                    if current_price >= (1 + self.threshold) * reference_price:
                        self.buy(self.amount_per_trade, date, trigger="dynamic_check")
                        
                elif self.threshold < 0:
                    if current_price <= (1 + self.threshold) * reference_price:
                        self.buy(self.amount_per_trade, date, trigger="dynamic_check")
            elif isinstance(self.threshold, tuple):
                price_range = sorted([(1 + self.threshold[0]) * reference_price, (1 + self.threshold[1]) * reference_price])
                if price_range[0] <= current_price <= price_range[1]:
                    self.buy(self.amount_per_trade, date, trigger="dynamic_check")

        if date >= self.end:
            raise StopChecking