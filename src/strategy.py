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
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            sizing_type: str = "static",
            manual_orders: list[dict] | None = None,
            name: str = "undefined_strategy"
            ):
        """Initializes the strategy state.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date (YYYY-MM-DD).
            end (str): End date (YYYY-MM-DD).
            capital (float): Initial capital.
            sf (StockFrame): Price data manager.
            sizing_type (str, optional): Default position sizing method.
                Options: "static" (fixed amount), "initial" (% of starting cap),
                "current" (% of current cap). Defaults to "static".
            manual_orders (list[dict] | None, optional): Configuration for manual orders
                to be executed on specific dates. Defaults to None.
            name (str, optional): Strategy name. Defaults to "undefined_strategy".

        Raises:
            ValueError: If `sizing_type` is not one of the recognized options.
        """

        self.name: str = name
        self.ticker: str = ticker
        self.start: str = start
        self.end: str = end
        self.sf: StockFrame = sf
        self.initial_capital: float = float(capital)
        self.fiat: float = float(capital)
        self.stock: float = 0.0
        self.profits: float | None = None
        self.operations: list[Operation] = []
        self.closed: bool = False
        
        if not manual_orders == None:
            self.manual_orders_config: list[dict] = manual_orders 
        else:
            self.manual_orders_config: list[dict] = [] 

        if sizing_type in ["static", "initial", "current"]:
            self.sizing_type: str = sizing_type
        else:
            raise ValueError(f"Sizing type '{sizing_type}' not recognized.")
        
    def _calculate_order_amount(
            self, 
            quantity: float, 
            override_sizing_type: str | None = None
            ) -> float:
        """Calculates the cash value of an order based on the sizing type.

        Internal helper to translate a generic `quantity` input into a specific
        monetary amount based on the selected sizing logic.

        Args:
            quantity (float): The raw input quantity (amount or percentage).
            override_sizing_type (str | None, optional): A specific sizing type for this calculation
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
        
        elif current_sizing == "initial":
            return self.initial_capital * quantity
            
        elif current_sizing == "current":
            return self.fiat * quantity
            
        else:
            raise ValueError(f"Sizing type '{current_sizing}' not recognized.")

    def buy(
            self,
            quantity: float,
            date: str,
            trigger: str = "manual",
            override_sizing_type: str | None = None
            ) -> None:
        """Executes a buy order (Long entry), robust to missing price data.

        Attempts to retrieve the asset price for the specific `date`. If data is 
        unavailable (e.g., market holiday), it automatically falls back to the 
        last valid historical price.

        Calculates the required cash based on the quantity and sizing type.
        If sufficient funds are available, converts cash to stock and logs a 
        successful operation.

        Args:
            quantity (float): Amount or percentage to buy.
            date (str): Date of execution (YYYY-MM-DD).
            trigger (str, optional): Reason for the trade. Defaults to "manual".
            override_sizing_type (str | None, optional): Override for position sizing.

        Raises:
            NotEnoughCashError: If `fiat` is less than the calculated order cost.
        """

        stock_price = self.sf.get_price_in(date)
        if stock_price == None:
            stock_price = self.sf.get_last_valid_price(date)
        
        if stock_price == None:
            print(f"Error in buy ({self.name}): No price found for {date}.")
            return

        cash_amount = round(self._calculate_order_amount(quantity, override_sizing_type=override_sizing_type),2)
        
        if cash_amount >= 0.01:
            if self.fiat - cash_amount > -0.01:
                self.fiat = round(self.fiat - cash_amount, 2)
                self.stock += float(round(cash_amount / stock_price, 8))
                self.operations.append(Operation("buy", cash_amount, self.ticker, stock_price, True, date, trigger))
            else:
                self.operations.append(Operation("buy", cash_amount, self.ticker, stock_price, False, date, trigger))
                raise NotEnoughCashError
    
    def buy_all(
            self,
            date: str,
            trigger: str = "manual"
            ) -> None:
        """Invests all available capital into the asset.

        A convenience method that triggers a "static" buy using the current
        `fiat` balance as the quantity.

        Args:
            date (str): Date of execution (YYYY-MM-DD).
            trigger (str, optional): Reason for the trade. Defaults to "manual".
        """

        stock_price = self.sf.get_price_in(date)
        if stock_price == None:
            stock_price = self.sf.get_last_valid_price(date)
        
        if stock_price == None:
            print(f"Error in buy_all ({self.name}): No price found for {date}.")
            return

        if self.fiat > 0:
            cash_spent = self.fiat
            stock_gained = float(round(cash_spent / stock_price, 8))
            
            self.fiat = 0.0
            self.stock += stock_gained
            
            self.operations.append(Operation("buy", cash_spent, self.ticker, stock_price, True, date, trigger))

    def sell(
            self,
            quantity: float,
            date: str,
            trigger: str = "manual",
            override_sizing_type: str | None = None
            ) -> None:
        """Executes a sell order (Long exit), robust to missing price data.

        Attempts to retrieve the asset price for the specific `date`. If data is 
        unavailable (e.g., market holiday), it automatically falls back to the 
        last valid historical price.

        Calculates the cash value of the stock to be sold.
        If sufficient stock is owned, converts stock to cash and logs a successful 
        operation.

        Args:
            quantity (float): Amount or percentage to sell.
            date (str): Date of execution (YYYY-MM-DD).
            trigger (str, optional): Reason for the trade. Defaults to "manual".
            override_sizing_type (str | None, optional): Override for position sizing.

        Raises:
            NotEnoughStockError: If `stock` holdings are less than the sell amount.
        """
        
        if override_sizing_type == None:
            current_sizing = self.sizing_type
        else:
            current_sizing = override_sizing_type

        stock_price = self.sf.get_price_in(date)
        if stock_price == None:
            stock_price = self.sf.get_last_valid_price(date)
        
        if stock_price == None:
            print(f"Error in sell ({self.name}): No price found for {date}.")
            return

        if current_sizing == "initial":
            cash_amount = round(self.stock * stock_price * quantity, 2)
        elif current_sizing == "current":
            cash_amount = round(self._calculate_order_amount(quantity, override_sizing_type=override_sizing_type),2)
        else:
            cash_amount = round(self._calculate_order_amount(quantity, override_sizing_type=override_sizing_type),2)
        
        if cash_amount >= 0.01:
            stock_amount = float(round(cash_amount / stock_price, 8))
            
            if self.stock - stock_amount >= -0.000001:
                self.fiat = round(float(self.fiat + cash_amount), 2)
                self.stock -= stock_amount
                self.operations.append(Operation("sell", cash_amount, self.ticker, stock_price, True, date, trigger))
            else:
                self.operations.append(Operation("sell", cash_amount, self.ticker, stock_price, False, date, trigger))
                raise NotEnoughStockError
        
    def sell_all(
            self,
            date: str,
            trigger: str = "manual"
            ) -> None:
        """Liquidates the entire position (Stock -> Cash), robust to missing price data.

        Attempts to retrieve the asset price for the specific `date`. If data is 
        unavailable (e.g., market holiday), it automatically falls back to the 
        last valid historical price to calculate the total liquidation value.

        Args:
            date (str): Date of execution (YYYY-MM-DD).
            trigger (str, optional): Reason for the trade. Defaults to "manual".
        """
        
        stock_price = self.sf.get_price_in(date)
        if stock_price == None:
            stock_price = self.sf.get_last_valid_price(date)
        
        if stock_price == None:
            return 

        if self.stock > 0:
            cash_value = round(self.stock * stock_price, 2)
            self.fiat = round(self.fiat + cash_value, 2)
            
            self.stock = 0.0
            
            self.operations.append(Operation("sell", cash_value, self.ticker, stock_price, True, date, trigger))

    def close_trade(
            self,
            date: str,
            trigger: str = "force_close"
            ) -> None:
        """Forces the closure of the trading position.

        Sells all holdings, calculates the final profits relative to the initial
        capital, and marks the strategy as closed. This is typically called at
        the end of a simulation or when a stop condition is met.

        Args:
            date (str): Date of closure (YYYY-MM-DD).
            trigger (str, optional): Reason for closure. Defaults to "force_close".
        """

        if not self.closed:
            self.sell_all(date, trigger = trigger)
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

    def print_performance(self) -> None:
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

    def print_operations(self) -> None:
        """Prints the description of every operation recorded in the log."""

        print(f"--- Operations Detail for {self.name} ({len(self.operations)} operations) ---")
        for operation in self.operations:
            print(operation.get_description())
    

    def get_successful_operations(self) -> list[str]:
        """Returns a list of descriptions for all successfully executed trades."""

        successful_operations = []
        for operation in self.operations:
            if operation.successful:
                successful_operations.append(operation.get_description())
        return successful_operations
            
    def get_failed_operations(self) -> list[str]:
        """Returns a list of descriptions for trades rejected due to insufficient funds/stock."""

        unsuccessful_operations = []
        for operation in self.operations:
            if not operation.successful:
                unsuccessful_operations.append(operation.get_description())
        return unsuccessful_operations

    def get_all_operations(self) -> list[str]:
        """Returns a list of descriptions for all attempted trades (both success and fail)."""

        operations = []
        for operation in self.operations:
            operations.append(operation.get_description())
        return operations
    
    def __add__(
            self, 
            strat2: "Strategy"
            ) -> "Strategy":
        """Overloads the `+` operator to combine strategies.

        Allows creating a `MultiStrategy` container by simply adding two strategy
        instances together (e.g., `strat1 + strat2`). Handles combinations of
        individual strategies and existing MultiStrategies.

        Args:
            strat2 (Strategy): The strategy to combine with this one.

        Returns:
            Strategy: A new container (MultiStrategy) holding both strategies.
        """

        from src.multi_strategy import MultiStrategy
        
        def get_sub_strats(s):
            if isinstance(s, MultiStrategy):
                return s.active_strategies
            return [s]
        
        combined_strats = get_sub_strats(self) + get_sub_strats(strat2)
        return MultiStrategy(combined_strats)

    def set_name(
            self, 
            name: str
            ) -> None:
        """Updates the identifier name of the strategy.

        Args:
            name (str): The new name for the strategy.
        """
        
        self.name = name
    
    def get_current_capital(
        self, 
        date: str
        ) -> float:
        """Calculates the total equity (Cash + Stock Value) on a specific date.

        Retrieves the asset price for the given date to determine the market value
        of held stocks. If price data is unavailable (e.g., holidays), it defaults
        to returning only the available cash component.

        Args:
            date (str): Date to evaluate (YYYY-MM-DD).

        Returns:
            float: Total portfolio value rounded to 2 decimal places.
        """
        
        price = self.sf.get_price_in(date)
        
        if price == None:
            return self.fiat
            
        stock_value = self.stock * price
        return round(self.fiat + stock_value, 2)

    def check_and_do(
            self, 
            date: str
            ) -> None:
        """Executes manual orders configured for the specific date.

        Iterates through the `manual_orders_config` list and executes any order
        whose scheduled date matches the current simulation date.

        Args:
            date (str): The current simulation date (YYYY-MM-DD).
        """
        for order in self.manual_orders_config:
            if order['date'] == date:
                order_type = order['type']
                amount = order['amount']
                sizing = order.get('override_sizing_type', self.sizing_type)

                try:
                    if order_type == "buy":
                        self.buy(amount, date, trigger="manual_order", override_sizing_type=sizing)
                    elif order_type == "buy_all":
                        self.buy_all(date, trigger="manual_order")
                    elif order_type == "sell":
                        self.sell(amount, date, trigger="manual_order", override_sizing_type=sizing)
                    elif order_type == "sell_all":
                        self.sell_all(date, trigger="manual_order")
                except (NotEnoughCashError, NotEnoughStockError):
                    print(f"Warning: Manual order {order_type} on {date} failed due to insufficient funds/stock.")

    def execute(self) -> None:
        """Runs the main strategy loop over the date range.

        Iterates day-by-day calling `check_and_do` to process manual orders or
        any other logic defined in subclasses. Closes the trade at the end.
        """
        for date in track(self.sf.index, description=f"Executing {self.name}..."):
            if self.start <= date <= self.end:
                self.check_and_do(date)
        
        self.close_trade(self.end)

    def execute_and_save(
            self,
            db_route: str
            ) -> None:
        """Executes the strategy simulation and persists daily performance metrics.

        Runs the strategy day-by-day over the configured date range. It specifically
        handles `NotEnoughStockError` by immediately closing the trade and stopping
        the simulation, which is critical for sell-focused strategies.

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
            except NotEnoughStockError:
                self.close_trade(date)
                break
            except StopChecking:
                break
            except Exception as e:
                print(f"Error in {self.name} on {date}: {e}")
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
            table_name = str(self.name)
            try:
                save_to_db(table_name, df_perf, db_name=db_route)
                print(f"Results saved to '{table_name}'")
            except Exception as e:
                print(f"Error saving results: {e}")