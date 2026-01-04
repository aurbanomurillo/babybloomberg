"""
Sell (Short/Exit) strategies based on price levels or relative movements.

This module defines strategies specialized in closing positions or selling assets.
It includes a static variant (`SellStrategy`) that sells at fixed prices or ranges,
and a dynamic variant (`DynamicSellStrategy`) that sells based on percentage
variations (trailing stops or profit taking) relative to a previous period.
"""

from src.strategy import *
from src.stockframe_manager import *

class SellStrategy(Strategy):
    """Static sell strategy based on absolute price levels.

    Enters the market immediately (buys all) at the start and then monitors the price
    to execute sell orders when specific static thresholds are met. Useful for
    setting fixed Take Profit or Stop Loss levels.

    Attributes:
        threshold (float | tuple[float, float]): Target price or sell price range.
        amount_per_trade (float): Amount of capital/stock value to sell per trade.
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
            name: str = "undefined_static_sell_strategy"
            ):
        """Initializes the sell strategy and executes an initial 'buy all'.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Value to sell per signal.
            threshold (float | tuple[float, float]):
                - If float: Exact price to trigger sell.
                - If tuple: Price range (min, max) to trigger sell.
            sizing_type (str, optional): Sizing type. Defaults to "static".
            name (str, optional): Strategy name.
        """

        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        self.threshold: str = threshold
        self.amount_per_trade: float = amount_per_trade
        self.buy_all(self.start, trigger="initial_restock")


    def check_and_do(
            self,
            date: str
            ) -> None:
        """Evaluates if the current price meets the static sell threshold.

        Checks if the price is within the target range or matches the target value.
        If so, executes a sell order.

        Args:
            date (str): Current date.

        Raises:
            StopChecking: If the simulation end date is reached.
        """

        current_price = self.sf.get_price_in(date)
        if type(self.threshold) == tuple:
            if self.start <= date < self.end and not current_price == None and self.threshold[0] <= current_price <= self.threshold[1]:
                self.sell(self.amount_per_trade, date, trigger="automatic_check")
        elif type(self.threshold) == float:
            if self.start <= date < self.end and not current_price == None and current_price == self.threshold:
                self.sell(self.amount_per_trade, date, trigger="automatic_check")
        if date >= self.end:
            raise StopChecking

    def execute(self) -> None:
        """Executes the main strategy loop.

        Iterates through dates. If stock runs out (`NotEnoughStockError`), it closes
        the trade and stops. Forces closure at the end of the period.
        """

        for date in track(self.sf.index, description=f"Executing {self.name}..."):
            try:
                self.check_and_do(date)
            except NotEnoughStockError:
                self.close_trade(date)
                break
            except StopChecking:
                break

        self.close_trade(self.end)

class DynamicSellStrategy(SellStrategy):
    """Dynamic sell strategy based on percentage variations (Trailing Stop/Take Profit).

    Decides to sell by comparing the current price with a past reference price
    (`trigger_lookback`). Useful for dynamic exits like Trailing Stops (selling on dips)
    or dynamic Take Profits (selling on spikes).

    Attributes:
        trigger_lookback (str): Time window for the reference price (e.g., "1 day").
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
            name: str = "undefined_dynamic_sell_strategy"
            ):
        """Initializes the dynamic sell strategy with validation.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date.
            end (str): End date.
            capital (float): Initial capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Value to sell per signal.
            threshold (float | tuple[float, float]): Percentage variation to trigger sell.
                - Ex: -0.05 implies selling if price drops 5% (Stop Loss/Trailing).
                - Ex: 0.10 implies selling if price rises 10% (Take Profit).
            trigger_lookback (str, optional): Lookback period. Defaults to "1 day".
            sizing_type (str, optional): Sizing type.
            name (str, optional): Strategy name.

        Raises:
            NotValidIntervalError: If threshold implies a drop of 100% or more.
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
            
        self.trigger_lookback:str = trigger_lookback

    def check_and_do(
            self,
            date: str
            ) -> None:
        """Evaluates price variation relative to the past to trigger a sell.

        Calculates the reference price from `trigger_lookback` ago.
        - Positive threshold: Sells if price rose >= X% (Take Profit).
        - Negative threshold: Sells if price fell >= X% (Stop Loss).

        Args:
            date (str): Current date.

        Raises:
            StopChecking: If end date is reached.
        """

        current_price = self.sf.get_price_in(date)
        reference_price = self.sf.get_last_valid_price(subtract_interval(date,self.trigger_lookback))

        if (self.start <= date < self.end and
                not current_price == None and
                not reference_price == None
                ):
            if isinstance(self.threshold,float):
                if self.threshold > 0:
                    if current_price >= (1 + self.threshold) * reference_price:
                        self.sell(self.amount_per_trade, date, trigger="dynamic_check")
                        
                elif self.threshold < 0:
                    if current_price <= (1 + self.threshold) * reference_price:
                        self.sell(self.amount_per_trade, date, trigger="dynamic_check")
            elif isinstance(self.threshold,tuple):
                price_range = sorted([(1+self.threshold[0])*reference_price,(1+self.threshold[1])*reference_price])
                if price_range[0] <= current_price <= price_range[1]:
                    self.sell(self.amount_per_trade, date, trigger="dynamic_check")

        if date >= self.end:
            raise StopChecking
        