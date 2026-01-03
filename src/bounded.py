"""
Bounded trading strategy with defined limits (Stop Loss, Take Profit, and Time).

This module implements a strategy that opens a position immediately at the start
and manages it based on strict exit rules: maximum allowable loss, target profit,
or maximum operation duration.
"""

from src.strategy import *
from src.stockframe_manager import *
from src.processing import *

class BoundedStrategy(Strategy):
    """Implements a 'buy and manage' strategy with price and time limits.

    This strategy enters the market with all available capital on the start date
    and monitors the position daily to close it if a Stop Loss, Take Profit,
    or maximum holding period is reached.

    Attributes:
        stop_loss (float): Sell price to cut losses.
        take_profit (float): Sell price to take profits.
        max_holding_period (str | None): Maximum time interval to hold the position.
        entry_price (float): Price at which the initial entry was executed.
    """
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            stop_loss: float,
            take_profit: float,
            max_holding_period: str = None,
            sizing_type:str = "static",
            name:str = "undefined_bounded_strategy"
            ):
        
        """Initializes the bounded strategy and executes the immediate market entry.

        Buys with all available capital at the start date price.
        Verifies if Stop Loss and Take Profit levels are logical relative to the entry price;
        prints a warning to the console if they are not.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial capital.
            sf (StockFrame): Price data manager.
            stop_loss (float): Absolute Stop Loss price.
            take_profit (float): Absolute Take Profit price.
            max_holding_period (str | None, optional): Maximum holding duration (e.g., "30 days", "2 weeks").
                Passed to the date processing function. Defaults to None.
            sizing_type (str, optional): Position sizing type. Defaults to "static".
            name (str, optional): Strategy name.
        """

        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)

        self.stop_loss:float = stop_loss
        self.take_profit:float = take_profit
        self.max_holding_period:str = max_holding_period        
        self.buy_all(self.start, trigger="initial_entry")
        self.entry_price:float = self.sf.get_price_in(self.start)
        if self.stop_loss >= self.entry_price:
            print(f"ADVERTENCIA: El Stop Loss ({self.stop_loss}) es mayor que el precio de entrada ({self.entry_price}). Se venderá inmediatamente.")
        if self.take_profit <= self.entry_price:
             print(f"ADVERTENCIA: El Take Profit ({self.take_profit}) es menor que el precio de entrada ({self.entry_price}). Se venderá inmediatamente.")

    def check_and_do(
            self,
            fecha:str
            ) -> None:
        """Verifies exit conditions for a specific date.

        Checks if the current price has hit the Stop Loss or Take Profit.
        Also checks if the maximum holding period has been exceeded by calculating
        the cutoff date from the start. If any condition is met, it closes the
        position and stops future execution.

        Args:
            fecha (str): Current date to verify (YYYY-MM-DD).

        Raises:
            StopChecking: Flow control signal indicating the position has been closed
                and the strategy should stop iterating over new dates.
        """

        current_price = self.sf.get_price_in(fecha)
        if not current_price == None:
            if current_price <= self.stop_loss:
                self.close_trade(fecha, trigger="stop_loss")
                raise StopChecking
            elif current_price >= self.take_profit:
                self.close_trade(fecha, trigger="take_profit")
                raise StopChecking

            elif not self.max_holding_period == None:
                fecha_hace_periodo = restar_intervalo(fecha, self.max_holding_period)
                if fecha_hace_periodo >= self.start:
                    self.close_trade(fecha, trigger="time_stop")
                    raise StopChecking

    def execute(self) -> None:
        """Executes the main strategy loop over the date range.

        Iterates day by day verifying exit conditions via `check_and_do`.
        Manages flow exceptions (`StopChecking`) to stop execution prematurely
        if the trade is closed. If the position is still open by the end date,
        it forces a close.
        """

        for fecha in track(self.sf.index, description=f"Executing {self.name}..."):
            if self.start <= fecha <= self.end:
                try:
                    self.check_and_do(fecha)
                except NotEnoughStockError:
                    break
                except StopChecking:
                    break
        if not self.closed:
            self.close_trade(self.end)
