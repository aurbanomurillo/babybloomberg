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
            sf:StockFrame
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

    def buy(
            self,
            cash_amount:float,
            fecha:str,
            trigger:str = "manual"
            ):

        stock_price = self.sf.get_price_in(fecha)
        
        if self.fiat - cash_amount >= 0:
            self.fiat -= cash_amount
            self.stock += float(round(cash_amount/stock_price, 8))
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, True, fecha, trigger))
        else:
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, False, fecha, trigger))
            raise NotEnoughCashError()
        
    def buy_all(
            self,
            fecha:str,
            trigger:str = "manual"
            ):
        self.buy(self.fiat, fecha, trigger)

    def sell(
            self,
            cash_amount:int,
            fecha:str,
            trigger:str = "manual"
            ):
        stock_price = self.sf.get_price_in(fecha)
        stock_amount = float(round(cash_amount/stock_price, 8))
        if self.stock - stock_amount >= -0.00000001:

            self.fiat += float(cash_amount)
            self.stock -= stock_amount
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, True, fecha, trigger))
        else:
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, False, fecha, trigger))
            raise NotEnoughStockError()
    
    def sell_all(
            self,
            fecha:str,
            trigger:str = "manual"
            ):
        stock_price = self.sf.get_price_in(fecha)
        self.sell(self.stock * stock_price, fecha, trigger)
        
    def close_trade(
            self,
            fecha:str,
            trigger:str = "force_close"
            ):
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

        from src.multi_strategy_manager import MultiStrat

        if isinstance(self, MultiStrat):
            if isinstance(strat2, MultiStrat):
                return MultiStrat(self.strats + strat2.strats)
            else:
                return MultiStrat(self.strats + [strat2])
        else:
            if isinstance(strat2, MultiStrat):
                return MultiStrat(strat2.strats + [self])
            else:
                return MultiStrat([self, strat2])

    def set_name(self, name:str):
        self.name = name