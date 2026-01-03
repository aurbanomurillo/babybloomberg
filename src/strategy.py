"""
Base definition for trading strategies and portfolio management.

This module defines the parent `Strategy` class, which handles the core mechanics
of any trading simulation: tracking capital (fiat) and assets (stock), executing
buy/sell orders, logging operations, and calculating performance metrics.
It also supports operator overloading to combine strategies into a `MultiStrategy`.
"""

from rich.progress import track
from src.exceptions import *
from src.database import *
from src.processing import *
from src.operations_manager import *
from src.stockframe_manager import *

class Strategy():
    """Base class representing a trading strategy.

    Manages the state of a single trading entity, including its available capital,
    stock inventory, and history of operations. It provides the fundamental methods
    to execute trades (`buy`, `sell`) and calculate final results.

    Attributes:
        name (str): Identifier for the strategy.
        ticker (str): Symbol of the asset being traded.
        start (str): Start date of the simulation.
        end (str): End date of the simulation.
        sf (StockFrame): Data source for asset prices.
        initial_capital (float): Starting cash amount.
        fiat (float): Current available cash.
        stock (float): Current quantity of the asset held.
        profits (float | None): Realized profits (calculated only upon closing).
        operations (list[Operation]): Log of all attempted transactions.
        closed (bool): Flag indicating if the strategy has finalized its position.
        sizing_type (str): Default method for calculating trade sizes ("static", etc.).
    """

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            sizing_type:str = "static",
            name:str = "undefined_strategy"
            ):
        """Initializes the strategy state.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial capital.
            sf (StockFrame): Price data manager.
            sizing_type (str, optional): Default position sizing method.
                Options: "static" (fixed amount), "percentage initial" (% of starting cap),
                "percentage current" (% of current cap). Defaults to "static".
            name (str, optional): Strategy name. Defaults to "undefined_strategy".

        Raises:
            ValueError: If `sizing_type` is not one of the recognized options.
        """

        self.name:str = name
        self.ticker:str = ticker
        self.start:str = start
        self.end:str = end
        self.sf:StockFrame = sf
        self.initial_capital:float = float(capital)
        self.fiat:float = float(capital)
        self.stock:float = 0.0
        self.profits:float | None = None
        self.operations:list[Operation] = []
        self.closed:bool = False

        if sizing_type in ["static", "percentage initial", "percentage current"]:
            self.sizing_type:str = sizing_type
        else:
            raise ValueError(f"Sizing type '{self.sizing_type}' not recognized.")
        
    def _calculate_order_amount(
            self, 
            quantity:float, 
            override_sizing_type:str = None
            ) -> float:
        """Calculates the cash value of an order based on the sizing type.

        Internal helper to translate a generic `quantity` input into a specific
        monetary amount based on the selected sizing logic.

        Args:
            quantity (float): The raw input quantity (amount or percentage).
            override_sizing_type (str, optional): A specific sizing type for this calculation
                that overrides the instance default.

        Returns:
            float: The calculated cash amount to be used in the trade.

        Raises:
            ValueError: If the sizing type is invalid.
        """

        if override_sizing_type == None:
            current_sizing = self.sizing_type
        else:
            current_sizing = override_sizing_type

        if current_sizing == "static":
            return quantity
        
        elif current_sizing == "percentage initial":
            return self.initial_capital * quantity
            
        elif current_sizing == "percentage current":
            return self.fiat * quantity
            
        else:
            raise ValueError(f"Sizing type '{self.sizing_type}' not recognized.")

    def buy(
            self,
            quantity:float,
            fecha:str,
            trigger:str = "manual",
            sizing_type:str = None
            ) -> None:
        """Executes a buy order (Long entry).

        Calculates the required cash based on the quantity and sizing type.
        If sufficient funds are available, converts cash to stock at the current
        price and logs a successful operation. If funds are insufficient, logs
        a failed operation and raises an error.

        Args:
            quantity (float): Amount or percentage to buy.
            fecha (str): Date of execution.
            trigger (str, optional): Reason for the trade. Defaults to "manual".
            sizing_type (str, optional): Override for position sizing.

        Raises:
            NotEnoughCashError: If `fiat` is less than the calculated order cost.
        """

        cash_amount = self._calculate_order_amount(quantity, override_sizing_type = sizing_type)
        
        if cash_amount >= 0.01:

            stock_price = self.sf.get_price_in(fecha)
            
            if self.fiat - cash_amount >= -0.000001:
                self.fiat = round(self.fiat - cash_amount, 2)
                self.stock += float(round(cash_amount/stock_price, 8))
                self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, True, fecha, trigger))
            else:
                self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, False, fecha, trigger))
                raise NotEnoughCashError
    
    def buy_all(
            self,
            fecha:str,
            trigger:str = "manual"
            ) -> None:
        """Invests all available capital into the asset.

        A convenience method that triggers a "static" buy using the current
        `fiat` balance as the quantity.

        Args:
            fecha (str): Date of execution.
            trigger (str, optional): Reason for the trade. Defaults to "manual".
        """

        self.buy(self.fiat, fecha, trigger=trigger, sizing_type="static")

    def sell(
            self,
            quantity:float,
            fecha:str,
            trigger:str = "manual",
            sizing_type:str = None
            ) -> None:
        """Executes a sell order (Long exit).

        Calculates the cash value of the stock to be sold.
        If sufficient stock is owned, converts stock to cash at the current
        price and logs a successful operation. If stock is insufficient, logs
        a failed operation and raises an error.

        Args:
            quantity (float): Amount or percentage to sell.
            fecha (str): Date of execution.
            trigger (str, optional): Reason for the trade. Defaults to "manual".
            sizing_type (str, optional): Override for position sizing.

        Raises:
            NotEnoughStockError: If `stock` holdings are less than the sell amount.
        """
        
        if not sizing_type == None:
            current_sizing = sizing_type
        else:
            current_sizing = self.sizing_type

        stock_price = self.sf.get_price_in(fecha)

        if current_sizing == "percentage current":
            cash_amount = round(self.stock * stock_price * quantity, 2)
        else:
            cash_amount = self._calculate_order_amount(quantity, override_sizing_type=sizing_type)
        
        if cash_amount >= 0.01:
        
            stock_amount = float(round(cash_amount/stock_price, 8))
            
            if self.stock - stock_amount >= -0.000001:

                self.fiat = round(float(self.fiat + cash_amount),2)
                self.stock -= stock_amount
                self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, True, fecha, trigger))
            else:
                self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, False, fecha, trigger))
                raise NotEnoughStockError
        
    def sell_all(
            self,
            fecha:str,
            trigger:str = "manual"
            ) -> None:
        """Liquidates the entire position.

        Calculates the total value of the currently held stock and executes
        a "static" sell for that full amount.

        Args:
            fecha (str): Date of execution.
            trigger (str, optional): Reason for the trade. Defaults to "manual".
        """
        
        stock_price = self.sf.get_price_in(fecha)
        self.sell(self.stock * stock_price, fecha, trigger, sizing_type="static")
        
    def close_trade(
            self,
            fecha:str,
            trigger:str = "force_close"
            ) -> None:
        """Forces the closure of the trading position.

        Sells all holdings, calculates the final profits relative to the initial
        capital, and marks the strategy as closed. This is typically called at
        the end of a simulation or when a stop condition is met.

        Args:
            fecha (str): Date of closure.
            trigger (str, optional): Reason for closure. Defaults to "force_close".
        """

        if not self.closed:
            self.sell_all(fecha, trigger = trigger)
            self.profits = round(self.fiat - self.initial_capital, 2)
            self.closed = True
    
    def get_profit(self) -> float:
        """Retrieves the absolute profit realized by the strategy.

        Returns:
            float: Total profit (Final Capital - Initial Capital).

        Raises:
            TradeNotClosed: If called before `close_trade` has been executed.
        """

        if not self.profits == None:
            return self.profits
        else:
            raise TradeNotClosed
    
    def get_returns(self) -> float:
        """Calculates the Return on Investment (ROI).

        Returns:
            float: The returns expressed as a decimal (e.g., 0.15 for 15%).
        """

        return round(self.profits / self.initial_capital, 8)

    def print_performance(self):
        """Prints a formatted summary of the strategy's performance.

        Displays the number of operations, initial and final capital, absolute
        profit, and percentage returns to the console.
        """

        try:
            print(f"-" * 50)
            print(f" --- Performance of {self.name} ---")
            print(f"{len(self.operations)} operations executed.")
            print(f"Initial capital = {round(self.initial_capital, 2)}$.")
            print(f"Final capital = {round(self.fiat, 2)}$.")
            print(f"Final profit = {round(self.get_profit(), 2)}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
            print(f"-" * 50)
        except TradeNotClosed:
            print(f"Trade not closed.")

    def print_operations(self):
        """Prints the description of every operation recorded in the log."""

        print(f"--- Detalle de Operaciones en {self.name} ({len(self.operations)} operaciones) ---")
        for operation in self.operations:
            print(operation.get_description())
    

    def get_succesful_operations(self) -> list[str]:
        """Returns a list of descriptions for all successfully executed trades."""

        succesful_operations = []
        for operation in self.operations:
            if operation.succesful:
                succesful_operations.append(operation.get_description())
        return succesful_operations
            
    def get_failed_operations(self) -> list[str]:
        """Returns a list of descriptions for trades rejected due to insufficient funds/stock."""

        unsuccesful_operations = []
        for operation in self.operations:
            if not operation.succesful:
                unsuccesful_operations.append(operation.get_description())
        return unsuccesful_operations

    def get_all_operations(self) -> list[str]:
        """Returns a list of descriptions for all attempted trades (both success and fail)."""

        operations = []
        for operation in self.operations:
            operations.append(operation.get_description())
        return operations
    
    def __add__(
            self, 
            strat2
            ):
        """Overloads the `+` operator to combine strategies.

        Allows creating a `MultiStrategy` container by simply adding two strategy
        instances together (e.g., `strat1 + strat2`). Handles combinations of
        individual strategies and existing MultiStrategies.

        Args:
            strat2 (Strategy | MultiStrategy): The strategy to combine with this one.

        Returns:
            MultiStrategy: A new container holding both strategies.
        """

        from src.multi_strategy import MultiStrategy
        if isinstance(self, MultiStrategy):
            if isinstance(strat2, MultiStrategy):
                return MultiStrategy(self.strats + strat2.strats)
            else:
                return MultiStrategy(self.strats + [strat2])
        else:
            if isinstance(strat2, MultiStrategy):
                return MultiStrategy(strat2.strats + [self])
            else:
                return MultiStrategy([self, strat2])

    def set_name(
            self, 
            name:str
            ) -> None:
        """Updates the identifier name of the strategy."""
        
        self.name = name

        