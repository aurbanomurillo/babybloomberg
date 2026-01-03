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
        
        self.type:str = type
        self.cash_amount:float = float(cash_amount)
        self.ticker:str = ticker
        self.stock_price:int = stock_price
        self.succesful:bool = succesful
        self.fecha:str = fecha
        self.trigger:str = trigger
        
    def get_description(self) -> str:
        if self.succesful:  
            return f"Succesful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.fecha}"
        else:
            return f"Unsuccesful {self.type} ({self.trigger}) operation of {self.cash_amount}$ worth of {self.ticker} at {self.stock_price}$ in {self.fecha}"
