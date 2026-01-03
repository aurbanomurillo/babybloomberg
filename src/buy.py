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
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade:float,
            threshold:tuple[float, float] | float,
            sizing_type:str = "static",
            name:str = "undefined_static_buy_strategy"
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
        self.threshold = threshold
        self.amount_per_trade = amount_per_trade

    def check_and_do(
            self,
            fecha:str
            ) -> None:
        """Evaluates if the current price meets the static threshold condition.

        Compares the closing price of the given date with the configured `threshold`.
        If the condition is met (strict equality for float or inclusion for tuple),
        it executes a buy order.

        Args:
            fecha (str): Current date to evaluate.

        Raises:
            StopChecking: If the current date has passed the strategy's end date.
        """

        precio_actual = self.sf.get_price_in(fecha)
        if type(self.threshold) == tuple:
            if self.start <= fecha < self.end and not precio_actual == None and self.threshold[0] <= precio_actual <= self.threshold[1]:
                self.buy(self.amount_per_trade, fecha, trigger="automatic_check")
        elif type(self.threshold) == float:
            if self.start <= fecha < self.end and not precio_actual == None and precio_actual == self.threshold:
                self.buy(self.amount_per_trade, fecha, trigger="automatic_check")
        if fecha >= self.end:
            raise StopChecking
    
    def execute(self) -> None:
        """Executes the main strategy loop.

        Iterates over all available dates. If a liquidity shortage is detected
        (`NotEnoughCashError`), it attempts to invest all remaining capital ("Buy All")
        and finishes the strategy. Closes any open position upon reaching the end date.
        """

        for fecha in track(self.sf.index, description=f"Executing {self.name}..."):
            try:
                self.check_and_do(fecha)
            except NotEnoughCashError:
                self.buy_all(fecha, trigger="last_automatic_check")
                break
            except StopChecking:
                break

        self.close_trade(self.end)


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
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade:float,
            threshold:tuple[float, float] | float,
            trigger_lookback:str = "1 day",
            sizing_type:str = "static",
            name:str = "undefined_dynamic_buy_strategy"
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
                raise NotValidIntervalError("El threshold no puede ser -100% o menor.")
        elif isinstance(threshold, tuple):
            if threshold[0] <= -1 or threshold[1] <= -1:
                raise NotValidIntervalError("Ningún límite del rango puede ser -100% o menor.")
        
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
            fecha:str
            ) -> None:
        """Evaluates price variation relative to the past (Lookback).

        Calculates the reference price using `trigger_lookback`.
        - If `threshold` is positive: Buys if current price has risen more than that %.
        - If `threshold` is negative: Buys if current price has dropped more than that %.
        - If `threshold` is tuple: Buys if current price falls within the projected range.

        Args:
            fecha (str): Current date to evaluate.

        Raises:
            StopChecking: If the end date is exceeded.
        """

        precio_actual = self.sf.get_price_in(fecha)
        precio_a_comparar = self.sf.get_last_valid_price(restar_intervalo(fecha,self.trigger_lookback))

        if (self.start <= fecha < self.end and
                not precio_actual == None and
                not precio_a_comparar == None
                ):
            if isinstance(self.threshold,float):
                if self.threshold > 0:
                    if precio_actual >= (1 + self.threshold) * precio_a_comparar:
                        self.buy(self.amount_per_trade, fecha, trigger="dynamic_check")
                        
                elif self.threshold < 0:
                    if precio_actual <= (1 + self.threshold) * precio_a_comparar:
                        self.buy(self.amount_per_trade, fecha, trigger="dynamic_check")
            elif isinstance(self.threshold,tuple):
                rango_precios = sorted([(1+self.threshold[0])*precio_a_comparar,(1+self.threshold[1])*precio_a_comparar])
                if rango_precios[0] <= precio_actual <= rango_precios[1]:
                    self.buy(self.amount_per_trade, fecha, trigger="dynamic_check")

        if fecha >= self.end:
            raise StopChecking
        