class Operation:

    def __init__(
            self,
            type:str,
            cash_amount:float,
            ticker:str,
            stock_price:int,
            succesful:bool,
            fecha:str,
            trigger:str = "Manual"
            ):
        
        self.type = type
        self.cash_amount = float(cash_amount)
        self.ticker = ticker
        self.stock_price = stock_price
        self.succesful = succesful
        self.fecha = fecha
        self.trigger = trigger
        
    def get_description(self):
        if self.succesful:  
            return f"Succesful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.fecha}"
        else:
            return f"Unsuccesful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.fecha}"
        
