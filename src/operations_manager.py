class Operation:

    def __init__(
            self,
            type:str,
            cash_amount:int,
            ticker:str,
            stock_price:int,
            succesful:bool,
            fecha:str):
        
        self.type = type
        self.cash_amount = int(cash_amount)
        self.ticker = ticker
        self.stock_price = stock_price
        self.succesful = succesful
        self.fecha = fecha
        
    def get_description(self):
        if self.succesful:
            return f"Succesful {self.type} operation of {self.cash_amount/100}$ worth of {self.ticker} at {self.stock_price/100}$ in {self.fecha}"
        else:
            return f"Unsuccesful {self.type} operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price/100}$ in {self.fecha}"
        
