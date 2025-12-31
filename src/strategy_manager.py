from decimal import Decimal
from rich.progress import track
from src.exceptions import *
from src.database import *
from src.processing import *
from src.operations_manager import *
from src.multi_strategy_manager import *


class Strategy():

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:int,
            sf:StockFrame
            ):
        
        self.ticker = ticker
        self.start = start
        self.end = end
        self.sf = sf
        self.initial_capital = capital
        self.fiat = capital
        self.stock = 0
        self.profits = None
        self.operations = []
        self.closed = False

    def buy(self, cash_amount:int, fecha:str):

        stock_price = self.sf.get_price_in(fecha)
        
        if self.fiat-cash_amount >= 0:
            self.fiat -= cash_amount
            self.stock += Decimal(round(cash_amount/stock_price, 8))
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, True, fecha))
        else:
            self.operations.append(Operation("compra", cash_amount, self.ticker, stock_price, False, fecha))
            raise NotEnoughCashError()
        
    def buy_all(self, fecha:str):
        self.buy(self.fiat, fecha)

    def sell(self, cash_amount:int, fecha:str):
        stock_price = self.sf.get_price_in(fecha)
        stock_amount = Decimal(round(cash_amount/stock_price, 8))
        if self.stock-stock_amount >= 0:

            self.fiat += int(cash_amount)
            self.stock -= stock_amount
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, True, fecha))
        else:
            self.operations.append(Operation("venta", cash_amount, self.ticker, stock_price, False, fecha))
            raise NotEnoughStockError()
    
    def sell_all(self, fecha:str):
        stock_price = self.sf.get_price_in(fecha)
        self.sell(self.stock * stock_price, fecha)
        
    def close_trade(self, fecha:str):
        self.sell_all(fecha)
        self.profits = self.fiat - self.initial_capital
        self.closed = True
    
    def get_profit(self) -> int:
        if not self.profits == None:
            return self.profits
        else:
            raise TradeNotClosed
    
    def get_returns(self) -> float:
        return round(self.profits / self.initial_capital, 8)

    def print_performance(self):
        try:
            for operation in self.operations:
                print(operation.get_description())
            print(f"-" * 50)
            print(f"{len(self.operations)} operations executed.")
            print(f"Initial capital = {self.initial_capital / 100}$.")
            print(f"Final capital = {self.fiat / 100}$.")
            print(f"Final profit = {self.get_profit() / 100}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
        except TradeNotClosed:
            print(f"Trade not closed.")

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


class AutoStrat(Strategy):

    def __init__(
        self,
        ticker:str,
        start:str,
        end:str,
        capital:int,
        sf:StockFrame,
        threshold_price:int,
        amount_per_trade:int,
        ):

        super().__init__(ticker, start, end, capital, sf)
        self.threshold_price = threshold_price
        self.amount_per_trade = amount_per_trade

    def __add__(self, other) -> MultiStrat:
        if isinstance(self, MultiStrat):
            if isinstance(other, MultiStrat):
                return MultiStrat(self.strats + other.strats)
            else:
                return MultiStrat(self.strats + [other])
        else:
            if isinstance(other, MultiStrat):
                return MultiStrat(other.strats + [self])
            else:
                return MultiStrat([self, other])
            

class BuyStrat(AutoStrat):
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:int,
            sf:StockFrame,
            threshold_price:int,
            amount_per_trade:int
            ):
        
        super().__init__(ticker, start, end, capital, sf, threshold_price, amount_per_trade)
    
    def check_and_do(self, fecha:str):
        if self.start <= fecha < self.end and self.sf.get_price_in(fecha) == self.threshold_price:
            self.buy(self.amount_per_trade, fecha)
        if fecha >= self.end:
            raise StopChecking
    
    def execute(self):
        for fecha in track(self.sf.index, description="Processing trades..."):
            try:
                self.check_and_do(fecha)
            except NotEnoughStockError:
                break
            except StopChecking:
                break

        self.close_trade(self.end)
    

class SellStrat(AutoStrat):
    
    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:int,
            sf:StockFrame,
            threshold_price:int,
            amount_per_trade:int
            ):
        
        super().__init__(ticker, start, end, capital, sf, threshold_price, amount_per_trade)
        self.buy_all(self.start)

    def check_and_do(self, fecha:str):
        if self.start<=fecha<self.end and self.sf.get_price_in(fecha) == self.threshold_price:
            self.sell(self.amount_per_trade, fecha)
        if fecha >= self.end:
            raise StopChecking

    def execute(self):
        for fecha in track(self.sf.index, description = "Processing trades..."):
            try:
                self.check_and_do(fecha)
            except NotEnoughStockError:
                break
            except StopChecking:
                break

        self.close_trade(self.end)
