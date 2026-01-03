from rich.progress import track
from src.exceptions import *
from src.database import *
from src.processing import *
from src.operations_manager import *
from src.stockframe_manager import *

class Strategy():

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            sizing_type:str = "static"
            ):
        
        self.ticker = ticker
        self.start = start
        self.end = end
        self.sf = sf
        self.initial_capital = float(capital)
        self.fiat = capital
        self.stock = 0.0
        self.profits = None
        self.operations:list[Operation] = []
        self.closed = False
        self.sizing_type = sizing_type

        if sizing_type in ["static", "percentage initial", "percentage current"]:
            self.sizing_type = sizing_type
        else:
            raise ValueError(f"Sizing type '{self.sizing_type}' not recognized.")
        
    def _calculate_order_amount(self, quantity:float, override_sizing_type:str =None):

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
            ):

        cash_amount = self._calculate_order_amount(quantity, override_sizing_type = sizing_type)
        stock_price = self.sf.get_price_in(fecha)
        
        if self.fiat - cash_amount >= -0.000001:
            self.fiat -= cash_amount
            self.stock += float(round(cash_amount/stock_price, 8))
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, True, fecha, trigger))
        else:
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, False, fecha, trigger))
            raise NotEnoughCashError
        
    def buy_all(
                self,
                fecha:str,
                trigger:str = "manual"
                ):
            self.buy(self.fiat, fecha, trigger=trigger, sizing_type="static")

    def sell(
            self,
            quantity:float,
            fecha:str,
            trigger:str = "manual",
            sizing_type:str = None
            ):
        
        if not sizing_type == None:
            current_sizing = sizing_type
        else:
            current_sizing = self.sizing_type

        stock_price = self.sf.get_price_in(fecha)

        if current_sizing == "percentage current":
            cash_amount = self.stock * stock_price * quantity
        else:
            cash_amount = self._calculate_order_amount(quantity, override_sizing_type=sizing_type)
        
        stock_amount = float(round(cash_amount/stock_price, 8))
        
        if self.stock - stock_amount >= -0.000001:

            self.fiat += float(cash_amount)
            self.stock -= stock_amount
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, True, fecha, trigger))
        else:
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, False, fecha, trigger))
            raise NotEnoughStockError
        
    def sell_all(
            self,
            fecha:str,
            trigger:str = "manual"
            ):
        
        stock_price = self.sf.get_price_in(fecha)
        self.sell(self.stock * stock_price, fecha, trigger, sizing_type="static")
        
    def close_trade(
            self,
            fecha:str,
            trigger:str = "force_close"
            ):
        if not self.closed:
            self.sell_all(fecha, trigger = trigger)
            self.profits = round(self.fiat - self.initial_capital, 2)
            self.closed = True
    
    def get_profit(self) -> float:
        if not self.profits == None:
            return self.profits
        else:
            raise TradeNotClosed
    
    def get_returns(self) -> float:
        return round(self.profits / self.initial_capital, 8)

    def print_performance(self):
        try:
            print(f"-" * 50)
            print(f"{len(self.operations)} operations executed.")
            print(f"Initial capital = {round(self.initial_capital, 2)}$.")
            print(f"Final capital = {round(self.fiat, 2)}$.")
            print(f"Final profit = {round(self.get_profit(), 2)}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
            print(f"-" * 50)
        except TradeNotClosed:
            print(f"Trade not closed.")

    def print_operations(self):
        for operation in self.operations:
            print(operation.get_description())
    

    def get_succesful_operations(self) -> list[str]:
        succesful_operations = []
        for operation in self.operations:
            if operation.succesful:
                succesful_operations.append(operation.get_description())
        return succesful_operations
            
    def get_failed_operations(self) -> list[str]:
        unsuccesful_operations = []
        for operation in self.operations:
            if not operation.succesful:
                unsuccesful_operations.append(operation.get_description())
        return unsuccesful_operations

    def get_all_operations(self) -> list[str]:
        operations = []
        for operation in self.operations:
            operations.append(operation.get_description())
        return operations
    
    def __add__(self, strat2):

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

    def set_name(self, name:str):
        self.name = name

        