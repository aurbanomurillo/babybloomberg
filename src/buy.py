"""
Buy (Long) strategies based on price levels or relative movements.

This module defines strategies specialized in opening long positions.
It includes a static variant (`BuyStrategy`) that operates on fixed prices or targets,
and a dynamic variant (`DynamicBuyStrategy`) that operates on percentage variations
(dips or breakouts) relative to a previous period.
"""

from src.strategy import *
from src.stockframe_manager import *

class BuyStrategy(Strategy):
    """Static buy strategy based on absolute price levels.

    Executes buy orders when the asset price reaches a specific value (target)
    or enters a determined price range. Manages liquidity by buying the defined
    amount or the remaining capital if it is insufficient.

    Attributes:
        threshold (float | tuple[float, float]): Target price or buy price range.
        amount_per_trade (float): Capital to invest in each operation.
    """
    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            amount_per_trade: float,
            threshold: tuple[float, float] | float,
            sizing_type: str = "static",
            name: str = "undefined_static_buy_strategy"
            ):
        """Initializes the buy strategy with a fixed price target.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial available capital.
            sf (StockFrame): Price data manager.
            amount_per_trade (float): Amount of money to invest per buy signal.
            threshold (float | tuple[float, float]):
                - If float: Exact price at which the buy will be triggered.
                - If tuple: Range (min, max) within which the buy will be triggered.
            sizing_type (str, optional): Sizing method ("static", "percentage", etc.).
            name (str, optional): Strategy identifier name.
        """

        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        self.threshold: tuple[float, float] | float = threshold
        self.amount_per_trade: float = amount_per_trade

    def check_and_do(
            self,
            date: str
            ) -> None:
        """Evaluates if the current price meets the static threshold condition.

        Compares the closing price of the given date with the configured `threshold`.
        If the condition is met (strict equality for float or inclusion for tuple),
        it executes a buy order.

        Args:
            date (str): Current date to evaluate.

        Raises:
            StopChecking: If the current date has passed the strategy's end date.
        """

        current_price = self.sf.get_price_in(date)
        
        if isinstance(self.threshold, tuple):
            if (self.start <= date < self.end and 
                not current_price == None and 
                self.threshold[0] <= current_price <= self.threshold[1]):
                self.buy(self.amount_per_trade, date, trigger="automatic_check")
                
        elif isinstance(self.threshold, float):
            if (self.start <= date < self.end and 
                not current_price == None and 
                current_price == self.threshold):
                self.buy(self.amount_per_trade, date, trigger="automatic_check")
                
        if date >= self.end:
            raise StopChecking
    
    def execute(self) -> None:
        """Executes the main strategy loop.

        Iterates over all available dates. If a liquidity shortage is detected
        (`NotEnoughCashError`), it attempts to invest all remaining capital ("Buy All")
        and finishes the strategy. Closes any open position upon reaching the end date.
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
        """Executes the strategy simulation and persists daily performance metrics.

        Runs the strategy day-by-day over the configured date range. It specifically
        handles `NotEnoughCashError` by triggering a final `buy_all` operation to
        invest any remaining capital before stopping the simulation.

        For each day, it triggers the trading logic, calculates the current equity
        (Cash + Stock Value), and logs the performance. Finally, the performance
        history is saved to the specified database.

        Args:
            db_route (str): The file path to the SQLite database where the performance
                table (named after the strategy) will be saved.
        """
        
        date_range = get_date_range(self.start, self.end)
        performance_log = []

        for date in track(date_range, description=f"Executing and saving {self.name}..."):
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
    """Dynamic buy strategy based on percentage variations (Momentum/Reversion).

    Unlike the static strategy, this class decides to buy by comparing the current
    price with the price from `n` periods ago (`trigger_lookback`).
    Allows buying on dips (Buy the Dip) if the threshold is negative, or on
    breakouts if the threshold is positive.

    Attributes:
        trigger_lookback (str): Reference time interval for price comparison (e.g., "1 day").
    """

    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            amount_per_trade: float,
            threshold: tuple[float, float] | float,
            trigger_lookback: str = "1 day",
            sizing_type: str = "static",
            name: str = "undefined_dynamic_buy_strategy"
            ):
        """Initializes the dynamic strategy by validating percentage thresholds.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date.
            end (str): End date.
            capital (float): Initial capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Capital per trade.
            threshold (float | tuple[float, float]): Percentage variation to trigger the buy.
                - Ex: -0.05 implies buying if the price drops 5%.
                - Ex: 0.10 implies buying if the price rises 10%.
            trigger_lookback (str, optional): Reference time window. Defaults to "1 day".
            sizing_type (str, optional): Sizing type.
            name (str, optional): Strategy name.

        Raises:
            NotValidIntervalError: If the threshold indicates a drop greater than 100% (<= -1.0),
                which is mathematically impossible for positive prices.
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
        """Evaluates price variation relative to the past (Lookback).

        Calculates the reference price using `trigger_lookback`.
        - If `threshold` is positive: Buys if current price has risen more than that %.
        - If `threshold` is negative: Buys if current price has dropped more than that %.
        - If `threshold` is tuple: Buys if current price falls within the projected range.

        Args:
            date (str): Current date to evaluate.

        Raises:
            StopChecking: If the end date is exceeded.
        """

        current_price = self.sf.get_price_in(date)
        reference_price = self.sf.get_last_valid_price(subtract_interval(date, self.trigger_lookback))

        if (self.start <= date < self.end and
                not current_price == None and
                not reference_price == None
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
