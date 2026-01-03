"""
Advanced strategy manager for multiple concurrent bounded trades.

This module implements strategies that do not trade directly but instead act as
factories or managers. They monitor market conditions and "spawn" independent
child strategies (`BoundedStrategy`) when specific criteria are met (price levels
or dynamic movements). Each child strategy manages its own lifecycle independently.
"""

from src.strategy import *
from src.bounded import *
from src.stockframe_manager import *
from src.exceptions import *

class MultiBoundedStrategy(Strategy):
    """Manager strategy that spawns child trades at specific price targets.

    This strategy monitors a list of target prices. When the market hits a target,
    it creates a new `BoundedStrategy` instance (a "child") with its own allocated
    capital, Stop Loss, and Take Profit. It aggregates the performance of all
    spawned children.

    Attributes:
        target_prices (list[float]): List of price levels that trigger a new trade.
        active_strategies (list[BoundedStrategy]): Currently open child trades.
        finished_strategies (list[BoundedStrategy]): Closed child trades.
        triggered_targets (set[float]): Set of targets already hit to prevent duplicate entries.
    """

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
            name:str = "undefined_multi_bounded_strategy"
            ):
        """Initializes the multi-bounded strategy with static price targets.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date.
            end (str): End date.
            capital (float): Total capital available for the manager.
            sf (StockFrame): Data manager.
            target_prices (list[float | tuple[float, float]]): Prices to watch.
                - Can be specific float values (limit orders).
                - Can be tuples representing price ranges.
            amount_per_trade (float): Capital allocated to each spawned child strategy.
            stop_loss_pct (float): Stop Loss percentage for children (e.g., -0.05 for -5%).
            take_profit_pct (float): Take Profit percentage for children (e.g., 0.10 for +10%).
            max_holding_period (int, optional): Max duration for children. Defaults to None.
            sizing_type (str, optional): Sizing type. Defaults to "static".
            name (str, optional): Strategy name.
        """

        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        
        self.target_prices:list[float] = sorted(target_prices, reverse=True)
        self.amount_per_trade:float = amount_per_trade
        
        self.stop_loss_pct:float = stop_loss_pct
        self.take_profit_pct:float = take_profit_pct
        self.max_holding_period:str = max_holding_period
        
        self.active_strategies: list[BoundedStrategy] = []
        self.finished_strategies: list[BoundedStrategy] = []
        
        self.triggered_targets:set[float] = set() 
        
        self.initial_ref_price:float = self.sf.get_last_valid_price(self.start)

    def _spawn_child(
            self,
            fecha:str,
            trigger_reason:str
            ) -> None:
        """Creates and activates a new child BoundedStrategy.

        Calculates absolute Stop Loss and Take Profit levels based on the current price
        and the configured percentages. Instantiates a `BoundedStrategy` and adds it
        to the list of active strategies if there is sufficient capital.

        Args:
            fecha (str): Date of the trigger event.
            trigger_reason (str): Description of why the child was spawned (e.g., "Target 150$ hit").
        """

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
            ) -> None:
        """Evaluates if any target price has been reached.

        Iterates through `target_prices`. If the current price matches a target
        that hasn't been triggered yet (checking against `triggered_targets`),
        it calls `_spawn_child`. Supports both exact price crossings and range inclusion.

        Args:
            fecha (str): Current date to evaluate.
        """

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
            ) -> None:
        """Main daily routine: checks triggers and updates active children.

        1. Checks if new strategies should be spawned (`_check_trigger`).
        2. Iterates over all `active_strategies` calling their `check_and_do`.
        3. Moves closed children from `active` to `finished` lists and reclaims their cash.

        Args:
            fecha (str): Current date.
        """

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
                
    def execute(self) -> None:
        """Runs the simulation over the entire date range.

        Iterates day-by-day calling `check_and_do`. At the end of the period,
        forces the closure of any remaining active child strategies.
        """

        for fecha in track(self.sf.index, description=f"Executing {self.name}..."):
            if self.start <= fecha <= self.end:
                self.check_and_do(fecha)
        
        self.close_trade(self.end)

    def close_trade(
            self,
            fecha:str,
            trigger:str="parent_force_close"
            ) -> None:
        """Forces the closure of all active child strategies.

        Called at the end of the simulation or when manually stopping the strategy.
        Collects capital and results from all children to calculate the final
        global profit.

        Args:
            fecha (str): Date of closure.
            trigger (str, optional): Reason for closure. Defaults to "parent_force_close".
        """

        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(fecha, trigger=trigger)
                self.fiat += strat.fiat
                self.finished_strategies.append(strat)
        
        self.active_strategies = []
        self.profits = round(self.fiat - self.initial_capital, 2)
        self.closed = True  

    def get_all_operations(self) -> list[str]:
        """Aggregates operations from all child strategies (active and finished).

        Returns:
            list[str]: A chronological list of descriptions for every buy/sell operation
                performed by any child strategy managed by this instance.
        """
        
        all_strats = self.active_strategies + self.finished_strategies
        all_operations: list[Operation] = []
        for strat in all_strats:
            all_operations.extend(strat.operations)
        
        all_operations.sort(key=lambda x: x.fecha)
        return [operation.get_description() for operation in all_operations]
    
    def print_operations(self) -> None:
        """Prints a detailed log of all operations across all sub-strategies."""

        print(f"--- Detalle de Operaciones en {self.name} ({len(self.finished_strategies) + len(self.active_strategies)} sub-estrategias) ---")
        for description in self.get_all_operations():
            print(description)

    def print_performance(self) -> None:
        """Prints a summary of the global performance, aggregating all sub-strategies."""

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
    """Manager strategy that spawns child trades based on dynamic price movements.

    Instead of static targets, this strategy watches for relative price changes
    (dips or breakouts) over a lookback window. When a movement exceeds the
    `trigger_pct`, it spawns a `BoundedStrategy`.

    Attributes:
        trigger_pct (float): Percentage change required to trigger a trade.
        trigger_lookback (str): Time window for the change (e.g., "1 day").
    """

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
            name:str = "undefined_multi_dynamic_bounded_strategy"
            ):
        """Initializes the dynamic multi-bounded strategy.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date.
            end (str): End date.
            capital (float): Total capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Capital per child strategy.
            stop_loss_pct (float): SL percentage for children.
            take_profit_pct (float): TP percentage for children.
            trigger_pct (float): Threshold to spawn a child (negative for dips, positive for breakouts).
            trigger_lookback (str, optional): Lookback period. Defaults to "1 day".
            max_holding_period (int, optional): Max duration for children.
            sizing_type (str, optional): Sizing type.
            name (str, optional): Strategy name.
        """
        
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
            ) -> None:
        """Evaluates if a dynamic price movement (dip/breakout) has occurred.

        Calculates the percentage change between the current price and the price
        at `trigger_lookback`. If the change meets the `trigger_pct` condition
        (e.g., drops more than 5%), it spawns a new child strategy.

        Args:
            fecha (str): Current date.
        """

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
