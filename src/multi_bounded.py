from src.strategy import *
from src.bounded import *
from src.stockframe_manager import *
from src.exceptions import *
from rich.progress import track

class MultiBoundedStrategy(Strategy):

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            target_prices: list[float|tuple[float,float]],
            amount_per_trade: float,
            stop_loss_pct: float,       
            take_profit_pct: float,
            max_holding_period: int = None,
            sizing_type:str = "static",
            name:str = "undefined"
            ):
        
        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        
        self.target_prices = sorted(target_prices, reverse=True)
        self.amount_per_trade = amount_per_trade
        
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_holding_period = max_holding_period
        
        self.active_strategies: list[BoundedStrategy] = []
        self.finished_strategies: list[BoundedStrategy] = []
        
        self.triggered_targets = set() 
        
        self.initial_ref_price = self.sf.get_last_valid_price(self.start)

    def _spawn_child(
            self,
            fecha:str,
            trigger_reason:str
            ):
        
        if self.fiat >= self.amount_per_trade:            

            self.fiat -= self.amount_per_trade
            current_price = self.sf.get_price_in(fecha)
            
            sl_absolute = current_price * (1 + self.stop_loss_pct)
            tp_absolute = current_price * (1 + self.take_profit_pct)
            
            new_strat = BoundedStrategy(
                ticker=self.ticker,
                start=fecha,     
                end=self.end,    
                capital=self.amount_per_trade,
                sf=self.sf,
                stop_loss=sl_absolute,
                take_profit=tp_absolute, 
                max_holding_period=self.max_holding_period
            )
            
            if new_strat.operations:
                new_strat.operations[0].trigger = trigger_reason

            self.active_strategies.append(new_strat)

    def _check_trigger(
            self,
            fecha:str
            ):
        current_price = self.sf.get_price_in(fecha)
        if not current_price == None:
            for target in self.target_prices:
                if not target in self.triggered_targets:
                    
                    condition_met = False
                    
                    if isinstance(target, float):
                        if target < self.initial_ref_price and current_price <= target:
                            condition_met = True
                        elif target > self.initial_ref_price and current_price >= target:
                            condition_met = True
                    
                    elif isinstance(target, tuple):
                        if target[0] <= current_price <= target[1]:
                            condition_met = True

                    if condition_met:
                        self._spawn_child(fecha, trigger_reason=f"Static target {target}$ hit")
                        self.triggered_targets.add(target)

    def check_and_do(
            self,
            fecha:str
            ):
        current_price = self.sf.get_price_in(fecha)
        if not current_price == None: 
            self._check_trigger(fecha)
            
            for strat in self.active_strategies[:]:
                try:
                    strat.check_and_do(fecha)
                except (StopChecking, NotEnoughStockError):
                    self.finished_strategies.append(strat)
                    self.active_strategies.remove(strat)
                    self.fiat += strat.fiat 
                
    def execute(self):
        for fecha in track(self.sf.index, description="Running Multi-Bounded..."):
            if self.start <= fecha <= self.end:
                self.check_and_do(fecha)
        
        self.close_trade(self.end)

    def close_trade(
            self,
            fecha:str,
            trigger:str="parent_force_close"
            ):
        
        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(fecha, trigger=trigger)
                self.fiat += strat.fiat
                self.finished_strategies.append(strat)
        
        self.active_strategies = []
        self.profits = round(self.fiat - self.initial_capital, 2)
        self.closed = True  

    def get_all_operations(self) -> list[str]:
        all_strats = self.active_strategies + self.finished_strategies
        all_operations: list[Operation] = []
        for strat in all_strats:
            all_operations.extend(strat.operations)
        
        all_operations.sort(key=lambda x: x.fecha)
        return [operation.get_description() for operation in all_operations]
    
    def print_operations(self):
        print(f"--- Detalle de Operaciones ({len(self.finished_strategies) + len(self.active_strategies)} sub-estrategias) ---")
        for description in self.get_all_operations():
            print(description)

    def print_performance(self):
        all_strats = self.active_strategies + self.finished_strategies
        
        total_operations = sum(len(strat.operations) for strat in all_strats)

        try:
            print(f"-" * 50)
            print(f" --- Performance of {self.name} ---")
            print(f"{total_operations} operations executed across {len(all_strats)} sub-strategies.")
            print(f"Initial capital = {round(self.initial_capital, 2)}$.")
            print(f"Final capital = {round(self.fiat, 2)}$.")
            print(f"Final profit = {round(self.get_profit(), 2)}$")
            print(f"Final returns (percentage) = {round(self.get_returns() * 100, 4)}%")
            print(f"-" * 50)
        except TradeNotClosed:
            print(f"Trade not closed.")

class MultiDynamicBoundedStrategy(MultiBoundedStrategy):

    def __init__(
            self,
            ticker:str,
            start:str,
            end:str,
            capital:float,
            sf:StockFrame,
            amount_per_trade: float,
            stop_loss_pct: float,       
            take_profit_pct: float,     
            trigger_pct: float,
            trigger_lookback:str = "1 day",
            max_holding_period: int = None,
            sizing_type:str = "static",
            name:str = "undefined"
            ):

        
        super().__init__(
            ticker, start, end, capital, sf, 
            target_prices=[], 
            amount_per_trade=amount_per_trade, 
            stop_loss_pct=stop_loss_pct, 
            take_profit_pct=take_profit_pct, 
            max_holding_period=max_holding_period,
            sizing_type = sizing_type,
            name = name
            )
        
        self.trigger_pct = trigger_pct
        self.trigger_lookback = trigger_lookback

    def _check_trigger(
            self,
            fecha:str
            ):
        
        current_price = self.sf.get_price_in(fecha)
        try:
            fecha_pasada_str = restar_intervalo(fecha, self.trigger_lookback)
        except Exception:
            return 

        precio_pasado = self.sf.get_last_valid_price(fecha_pasada_str)
        
        if precio_pasado and precio_pasado > 0:
            variacion = (current_price - precio_pasado) / precio_pasado
            
            condition_met = False
            
            if self.trigger_pct < 0:
                if variacion <= self.trigger_pct:
                    condition_met = True
            
            elif self.trigger_pct > 0:
                if variacion >= self.trigger_pct:
                    condition_met = True

            if condition_met:
                if self.trigger_pct < 0:
                    self._spawn_child(fecha, trigger_reason=f"Dip {round(variacion*100, 2)}% in {self.trigger_lookback}")
                else:
                    self._spawn_child(fecha, trigger_reason=f"Breakout {round(variacion*100, 2)}% in {self.trigger_lookback}")
