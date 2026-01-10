"""Advanced strategy manager for multiple concurrent bounded trades.

This module implements strategies that act as "Manager" or "Factory" entities.
Instead of executing trades directly, they monitor market conditions (static price
levels or dynamic momentum) and spawn independent child instances of
`BoundedStrategy` when criteria are met.

The manager aggregates the capital, risk, and performance of all its children
into a single consolidated portfolio.
"""

from src.strategy import *
from src.bounded import *
from src.stockframe_manager import *
from src.exceptions import *

class MultiBoundedStrategy(Strategy):
    """Orchestrates multiple concurrent bounded trades based on static price targets.

    This strategy acts as a container that holds a pool of capital ("fiat").
    It monitors a list of static price targets. When a target is hit, it "spawns"
    (instantiates) a new `BoundedStrategy` child, allocates a portion of capital
    to it, and delegates the trade management to that child.

    Attributes:
        target_prices (list[float | tuple[float, float]]): The list of price
            levels or ranges that trigger new trades.
        active_strategies (list[BoundedStrategy]): The list of currently running
            child strategies.
        finished_strategies (list[BoundedStrategy]): The list of completed
            child strategies (closed positions).
        triggered_targets (set[float]): A set of targets that have already been
            hit to prevent duplicate entries for the same price level.
    """

    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            target_prices: list[float|tuple[float,float]],
            amount_per_trade: float,
            stop_loss: float,
            take_profit: float,
            sl_type: str = "%",
            tp_type: str = "%",
            max_holding_period: str | None = None,
            sizing_type: str = "static",
            name: str = "undefined_multi_bounded_strategy"
            ):
        """Initializes the multi-bounded manager with static targets.

        Validates the start date and sorts the target prices to optimize triggering.
        Also initializes the tracking sets for active/finished children.

        Note:
            If the `start` date falls on a non-trading day, it is automatically
            advanced to the next valid date in the dataset.

        Args:
            ticker (str): The asset symbol (e.g., "BTC-USD").
            start (str): The simulation start date (YYYY-MM-DD).
            end (str): The simulation end date (YYYY-MM-DD).
            capital (float): The total capital available to the manager to distribute.
            sf (StockFrame): The data manager containing price history.
            target_prices (list[float | tuple[float, float]]): The prices to watch.
                - Float: Exact limit price to trigger entry.
                - Tuple: Price range (min, max) to trigger entry.
            amount_per_trade (float): The base amount of capital to allocate to
                each spawned child strategy.
            stop_loss (float): The Stop Loss setting passed to children.
            take_profit (float): The Take Profit setting passed to children.
            sl_type (str, optional): Stop Loss type ("$" for absolute, "%" for
                percentage). Defaults to "%".
            tp_type (str, optional): Take Profit type ("$" for absolute, "%" for
                percentage). Defaults to "%".
            max_holding_period (str | None, optional): The maximum duration each
                child strategy is allowed to remain open. Defaults to None.
            sizing_type (str, optional): The method for sizing child allocations.
                Defaults to "static".
            name (str, optional): A unique identifier for the strategy.
                Defaults to "undefined_multi_bounded_strategy".
        """

        super().__init__(ticker, start, end, capital, sf, sizing_type=sizing_type, name=name)
        
        if not self.start in self.sf.index.tolist():
            valid_dates = self.sf.index[self.sf.index >= self.start]
            if not valid_dates.empty:
                new_start = valid_dates[0]
                self.start = new_start
                self.initial_ref_price: float = self.sf.get_last_valid_price(self.start)
            else:
                self.initial_ref_price: float = None
        else:
            self.initial_ref_price: float = self.sf.get_last_valid_price(self.start)
        
        self.target_prices: list = sorted(
            target_prices, 
            key=lambda x: x if isinstance(x, (int, float)) else x[0], 
            reverse=True
        )
        self.amount_per_trade: float = amount_per_trade
        
        self.stop_loss: float = stop_loss
        self.take_profit: float = take_profit
        self.sl_type: str = sl_type
        self.tp_type: str = tp_type
        
        self.max_holding_period: str | None = max_holding_period
        
        self.active_strategies: list[BoundedStrategy] = []
        self.finished_strategies: list[BoundedStrategy] = []
        
        self.triggered_targets: set[float] = set()

    def _spawn_child(
            self,
            date: str,
            trigger_reason: str
            ) -> None:
        """Instantiates and activates a new child BoundedStrategy.

        Calculates the required capital allocation based on the manager's
        `sizing_type`. If sufficient fiat funds are available, the cash is
        deducted from the manager and transferred to the new child instance.

        Args:
            date (str): The date on which the child strategy is created.
            trigger_reason (str): A descriptive note explaining why the spawn
                occurred (e.g., "Static target 150$ hit").
        """

        allocation = 0.0

        if self.sizing_type == "initial":
            allocation = self.initial_capital * self.amount_per_trade
        
        elif self.sizing_type == "current":
            allocation = self.fiat * self.amount_per_trade
            
        else: 
            allocation = self.amount_per_trade
        
        if allocation < 0.01:
            return

        if self.fiat >= allocation:            
            allocation = round(allocation, 2)
            
            self.fiat = round(self.fiat - allocation, 2)
            
            new_strat = BoundedStrategy(
                ticker=self.ticker,
                start=date,     
                end=self.end,    
                capital=allocation,
                sf=self.sf,
                stop_loss=self.stop_loss,
                take_profit=self.take_profit,
                sl_type=self.sl_type,
                tp_type=self.tp_type,
                max_holding_period=self.max_holding_period,
                name=f"{self.name}_child_{date}"
            )            
            
            if new_strat.operations:
                new_strat.operations[0].trigger = trigger_reason

            self.active_strategies.append(new_strat)
            
    def _check_trigger(
            self,
            date: str
            ) -> None:
        """Evaluates static price targets against the current market price.

        Iterates through the configured `target_prices`. If the current price
        satisfies a target condition (crossing a specific price or entering a
        range) AND that target has not been triggered previously, it calls
        `_spawn_child`.

        Args:
            date (str): The current simulation date (YYYY-MM-DD).
        """

        current_price = self.sf.get_price_in(date)
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
                        self._spawn_child(date, trigger_reason=f"Static target {target}$ hit")
                        self.triggered_targets.add(target)

    def check_and_do(
            self,
            date: str
            ) -> None:
        """Orchestrates the daily routine for the manager and its children.

        1. Checks triggers to potentially spawn new child strategies.
        2. Delegates execution to all currently `active_strategies`.
        3. Monitors children for completion: if a child finishes (due to SL/TP/Time),
           it is moved to `finished_strategies` and its capital is reclaimed.

        Args:
            date (str): The current simulation date.
        """

        super().check_and_do(date)
        current_price = self.sf.get_price_in(date)
        if not current_price == None: 
            self._check_trigger(date)
            
            for strat in self.active_strategies[:]:
                try:
                    strat.check_and_do(date)
                except (StopChecking, NotEnoughStockError):
                    self.finished_strategies.append(strat)
                    self.active_strategies.remove(strat)
                    self.fiat += strat.fiat 
                
    def execute(self) -> None:
        """Runs the complete strategy simulation over the date range.

        Iterates daily, managing the lifecycle of child strategies. At the end
        of the simulation, it forces the closure of any children that are still
        active to realize final profits.
        """

        for date in track(self.sf.index, description=f"Executing {self.name}..."):
            if self.start <= date <= self.end:
                self.check_and_do(date)
        
        self.close_trade(self.end)

    def close_trade(
            self,
            date: str,
            trigger: str="parent_force_close"
            ) -> None:
        """Forces the closure of all active child strategies.

        Typically called at the end of the simulation. Triggers the `close_trade`
        method of every active child, reclaims their final capital into the
        manager's fiat pool, and calculates global profitability.

        Args:
            date (str): The date of closure.
            trigger (str, optional): Reason for closure. Defaults to "parent_force_close".
        """

        for strat in self.active_strategies:
            if not strat.closed:
                strat.close_trade(date, trigger=trigger)
                self.fiat += strat.fiat
                self.finished_strategies.append(strat)
        
        self.active_strategies = []
        self.profits = round(self.fiat - self.initial_capital, 2)
        self.closed = True  

    def get_all_operations(self) -> list[str]:
        """Aggregates operations from all managed child strategies.

        Returns:
            list[str]: A chronological list of descriptions for every operation
                performed by any child strategy (active or finished).
        """
        
        all_strats = self.active_strategies + self.finished_strategies
        all_operations: list[Operation] = []
        for strat in all_strats:
            all_operations.extend(strat.operations)
        
        all_operations.sort(key=lambda x: x.date)
        return [operation.get_description() for operation in all_operations]
    
    def print_operations(self) -> None:
        """Prints a consolidated log of all operations across the sub-strategies."""

        print(f"--- Operations Detail for {self.name} ({len(self.finished_strategies) + len(self.active_strategies)} sub-strategies) ---")
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
    """Manager strategy that spawns child trades based on dynamic price momentum.

    This strategy extends `MultiBoundedStrategy` but replaces static price
    targets with a dynamic momentum check. It monitors the percentage change
    relative to a past window (Lookback).

    - If `trigger_pct` < 0: Spawns children on Dips (Buying weakness).
    - If `trigger_pct` > 0: Spawns children on Breakouts (Buying strength).

    Attributes:
        trigger_pct (float): The percentage threshold to trigger a new trade.
        trigger_lookback (str): The time interval for calculating momentum.
    """

    def __init__(
            self,
            ticker: str,
            start: str,
            end: str,
            capital: float,
            sf: StockFrame,
            amount_per_trade: float,
            stop_loss: float,       
            take_profit: float,     
            trigger_pct: float,
            sl_type: str = "%",
            tp_type: str = "%",
            trigger_lookback: str = "1 day",
            max_holding_period: str = None,
            sizing_type: str = "static",
            name: str = "undefined_multi_dynamic_bounded_strategy"
            ):
        """Initializes the dynamic multi-bounded manager.

        Args:
            ticker (str): Asset symbol.
            start (str): Start date.
            end (str): End date.
            capital (float): Total manager capital.
            sf (StockFrame): Data manager.
            amount_per_trade (float): Capital allocated per child.
            stop_loss (float): SL setting for children.
            take_profit (float): TP setting for children.
            trigger_pct (float): Threshold to spawn a child.
                - Negative (e.g., -0.05) for dips.
                - Positive (e.g., 0.05) for breakouts.
            sl_type (str, optional): SL type ("$" or "%"). Defaults to "%".
            tp_type (str, optional): TP type ("$" or "%"). Defaults to "%".
            trigger_lookback (str, optional): Lookback window. Defaults to "1 day".
            max_holding_period (str, optional): Max child duration.
            sizing_type (str, optional): Allocation method.
            name (str, optional): Strategy name.
        """
        
        super().__init__(
            ticker=ticker, 
            start=start, 
            end=end, 
            capital=capital, 
            sf=sf, 
            target_prices=[],
            amount_per_trade=amount_per_trade, 
            stop_loss=stop_loss, 
            take_profit=take_profit, 
            sl_type=sl_type,
            tp_type=tp_type,
            max_holding_period=max_holding_period,
            sizing_type=sizing_type,
            name=name
            )
        
        self.trigger_pct: float = trigger_pct
        self.trigger_lookback: str = trigger_lookback

    def _check_trigger(
            self,
            date: str
            ) -> None:
        """Evaluates price momentum against the dynamic percentage threshold.

        Calculates the percentage change between the current price and the
        historical price from `trigger_lookback` ago.
        
        If `pct_change` exceeds `trigger_pct` (in the configured direction),
        it calls `_spawn_child`.

        Args:
            date (str): The current simulation date.
        """

        current_price = self.sf.get_price_in(date)
        try:
            lookback_date_str = subtract_interval(date, self.trigger_lookback)
        except Exception:
            return 

        reference_price = self.sf.get_last_valid_price(lookback_date_str)
        
        if reference_price and reference_price > 0:
            pct_change = (current_price - reference_price) / reference_price
            
            condition_met = False
            
            if self.trigger_pct < 0:
                if pct_change <= self.trigger_pct:
                    condition_met = True
            
            elif self.trigger_pct > 0:
                if pct_change >= self.trigger_pct:
                    condition_met = True

            if condition_met:
                if self.trigger_pct < 0:
                    self._spawn_child(date, trigger_reason=f"Dip {round(pct_change*100, 2)}% in {self.trigger_lookback}")
                else:
                    self._spawn_child(date, trigger_reason=f"Breakout {round(pct_change*100, 2)}% in {self.trigger_lookback}")

    def get_current_capital(
            self, 
            date: str
            ) -> float:
        """Calculates the total consolidated equity of the manager.

        Aggregates the unallocated cash ("fiat") held by the manager plus
        the current total value (equity) of all active child strategies.

        Args:
            date (str): Date to evaluate (YYYY-MM-DD).

        Returns:
            float: Total consolidated portfolio value rounded to 2 decimal places.
        """
        
        active_children_capital = 0
        for strat in self.active_strategies:
            active_children_capital += strat.get_current_capital(date)
            
        return round(self.fiat + active_children_capital, 2)