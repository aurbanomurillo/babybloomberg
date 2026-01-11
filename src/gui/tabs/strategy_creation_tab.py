"""
Strategy factory and management interface.

This module defines the StrategyCreationTab class, which serves as a central
hub for configuring, instantiating, combining, executing, and analyzing
various trading strategies supported by the application.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext
import copy
from typing import List, Dict, Tuple, Any, Set
import pandas as pd
from datetime import datetime, timedelta
from src.database import get_existing_tickers, get_sf_from_sqlite
from src.strategy import Strategy
from src.bounded import BoundedStrategy
from src.buy import BuyStrategy, DynamicBuyStrategy
from src.sell import SellStrategy, DynamicSellStrategy
from src.multi_bounded import MultiBoundedStrategy, MultiDynamicBoundedStrategy
from src.multi_strategy import MultiStrategy

class StrategyCreationTab(ttk.Frame):
    """
    A GUI tab for creating, managing, and executing trading strategies.

    This class provides a dynamic form that adjusts based on the selected strategy
    type. It allows users to define parameters (capital, dates, thresholds),
    instantiate strategy objects, execute them (with or without database saving),
    and visualize the results (performance metrics and operations logs).

    It also supports advanced features like combining multiple strategies into
    a MultiStrategy and recursive operation tracking.

    Attributes:
        STRATEGY_TYPES (dict): Mapping of display names to Strategy classes.
        SIZING_OPTIONS (list): Available position sizing methods.
        PRICE_OPTIONS (list): Available price calculation methods ($ or %).
        ORDER_TYPES (list): Available manual order types.
    """

    STRATEGY_TYPES = {
        "Manual (Base)": Strategy,
        "Buy (Dynamic/Dip)": DynamicBuyStrategy,
        "Buy (Static Price)": BuyStrategy,
        "Sell (Dynamic/Trailing)": DynamicSellStrategy,
        "Sell (Static Price)": SellStrategy,
        "Bounded (SL/TP/Time)": BoundedStrategy,
        "Multi Bounded": MultiBoundedStrategy,
        "Multi Dynamic Bounded": MultiDynamicBoundedStrategy
    }

    SIZING_OPTIONS = ["$", "% Initial", "% Current"]
    PRICE_OPTIONS = ["$", "%"]
    ORDER_TYPES = ["buy", "buy_all", "sell", "sell_all"]

    def __init__(
            self,
            parent: tk.Widget
            ) -> None:
        """
        Initializes the strategy creation tab.

        Sets up the Tkinter variables for form inputs and initializes the
        split-panel layout (configuration on the left, strategy list on the right).

        Args:
            parent (tk.Widget): The parent widget to which this frame belongs.
        """

        super().__init__(parent)

        self.var_name = tk.StringVar(value="My_Strategy")
        self.var_ticker = tk.StringVar()
        self.var_capital = tk.DoubleVar(value=10000.0)
        self.var_start = tk.StringVar(value="2020-01-01")
        self.var_end = tk.StringVar(value="2026-01-01")
        self.var_strat_type = tk.StringVar()

        self.var_amount = tk.DoubleVar(value=1000.0)
        self.var_sizing_type = tk.StringVar(value="$")

        self.var_sl = tk.DoubleVar(value=0.0)
        self.var_sl_type = tk.StringVar(value="$")
        self.var_tp = tk.DoubleVar(value=0.0)
        self.var_tp_type = tk.StringVar(value="$")

        self.target_rows: list[dict[str, Any]] = []

        self.var_hold = tk.StringVar(value="30 days")
        self.var_use_hold = tk.BooleanVar(value=True)
        self._last_hold_val = "30 days"

        self.var_threshold = tk.DoubleVar(value=0.0)
        self.var_lookback = tk.StringVar(value="1 day")

        self.var_use_range = tk.BooleanVar(value=False)
        self.var_thresh_min = tk.DoubleVar(value=0.0)
        self.var_thresh_max = tk.DoubleVar(value=0.0)

        self.manual_orders: list[dict[str, Any]] = []
        self.created_strategies_data: list[dict[str, Any]] = []

        self._init_ui()

    def _init_ui(self) -> None:
        """
        Configures the main split-pane layout.
        """

        self.main_pane = ttk.PanedWindow(self, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=5, pady=5)

        self.left_panel = ttk.Frame(self.main_pane)
        self.main_pane.add(self.left_panel, weight=3)

        self.right_panel = ttk.Frame(self.main_pane)
        self.main_pane.add(self.right_panel, weight=2)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        """
        Constructs the left panel containing configuration inputs.

        Includes general settings (Name, Ticker, Capital, Dates) and dynamic
        parameter inputs based on the selected strategy type.
        """

        common_frame = ttk.LabelFrame(self.left_panel, text="General Configuration", padding=10)
        common_frame.pack(fill="x", padx=10, pady=5)

        grid_opts = {'padx': 5, 'pady': 5, 'sticky': 'w'}

        ttk.Label(common_frame, text="Strategy Name:").grid(row=0, column=0, **grid_opts)
        ttk.Entry(common_frame, textvariable=self.var_name).grid(row=0, column=1, **grid_opts)

        ttk.Label(common_frame, text="Ticker:").grid(row=0, column=2, **grid_opts)
        self.combo_ticker = ttk.Combobox(common_frame, textvariable=self.var_ticker, state="readonly")
        self.combo_ticker.grid(row=0, column=3, **grid_opts)

        ttk.Button(common_frame, text="↻", width=3, command=self._refresh_tickers).grid(row=0, column=4, **grid_opts)

        self._refresh_tickers()

        ttk.Label(common_frame, text="Initial Capital ($):").grid(row=1, column=0, **grid_opts)
        ttk.Entry(common_frame, textvariable=self.var_capital).grid(row=1, column=1, **grid_opts)

        ttk.Label(common_frame, text="Start Date (YYYY-MM-DD):").grid(row=2, column=0, **grid_opts)
        ttk.Entry(common_frame, textvariable=self.var_start).grid(row=2, column=1, **grid_opts)

        ttk.Label(common_frame, text="End Date (YYYY-MM-DD):").grid(row=2, column=2, **grid_opts)
        ttk.Entry(common_frame, textvariable=self.var_end).grid(row=2, column=3, **grid_opts)

        type_frame = ttk.Frame(self.left_panel, padding=10)
        type_frame.pack(fill="x", padx=10)

        ttk.Label(type_frame, text="Select Strategy Type:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.combo_type = ttk.Combobox(type_frame, textvariable=self.var_strat_type, state="readonly", width=30)
        self.combo_type['values'] = list(self.STRATEGY_TYPES.keys())
        self.combo_type.pack(side="left", padx=5)
        self.combo_type.bind("<<ComboboxSelected>>", self._on_type_changed)

        self.specific_frame = ttk.LabelFrame(self.left_panel, text="Specific Parameters", padding=10)
        self.specific_frame.pack(fill="both", expand=True, padx=10, pady=5)

        btn_frame = ttk.Frame(self.left_panel, padding=10)
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.btn_create = ttk.Button(btn_frame, text="Create & Add to List", command=self._create_strategy_dispatcher)
        self.btn_create.pack(side="right")

        self.combo_type.current(0)
        self._on_type_changed(None)

    def _build_right_panel(self) -> None:
        """
        Constructs the right panel containing the list of created strategies.

        Includes the Treeview for displaying strategies and action buttons
        for execution, deletion, and combination.
        """

        lbl_title = ttk.Label(self.right_panel, text="Strategy List", font=("Arial", 10, "bold"))
        lbl_title.pack(pady=10)

        cols = ("check", "name", "type", "ticker", "perf", "ops")
        self.tree_list = ttk.Treeview(self.right_panel, columns=cols, show="headings", selectmode="browse")

        self.tree_list.heading("check", text="✔")
        self.tree_list.heading("name", text="Name")
        self.tree_list.heading("type", text="Type")
        self.tree_list.heading("ticker", text="Ticker")
        self.tree_list.heading("perf", text="Perf")
        self.tree_list.heading("ops", text="Ops")

        self.tree_list.column("check", width=30, anchor="center", stretch=False)
        self.tree_list.column("name", width=120)
        self.tree_list.column("type", width=120)
        self.tree_list.column("ticker", width=60)
        self.tree_list.column("perf", width=40, anchor="center", stretch=False)
        self.tree_list.column("ops", width=40, anchor="center", stretch=False)

        scrollbar = ttk.Scrollbar(self.right_panel, orient="vertical", command=self.tree_list.yview)
        self.tree_list.configure(yscroll=scrollbar.set)

        self.tree_list.pack(side="top", fill="both", expand=True, padx=5)
        scrollbar.pack(side="right", fill="y")

        self.tree_list.bind("<Button-1>", self._on_tree_click)

        action_frame = ttk.Frame(self.right_panel, padding=5)
        action_frame.pack(fill="x", side="bottom")

        row1 = ttk.Frame(action_frame)
        row1.pack(fill="x", pady=2)

        self.btn_exec = ttk.Button(row1, text="Execute Selected", command=lambda: self._execute_selected(save=False))
        self.btn_exec.pack(side="left", expand=True, fill="x", padx=1)

        self.btn_exec_save = ttk.Button(row1, text="Exec & Save Selected",
                                        command=lambda: self._execute_selected(save=True))
        self.btn_exec_save.pack(side="left", expand=True, fill="x", padx=1)

        row2 = ttk.Frame(action_frame)
        row2.pack(fill="x", pady=2)
        ttk.Button(row2, text="Sum Selected (+)", command=self._sum_strategies).pack(side="left", expand=True, fill="x",
                                                                                     padx=1)
        ttk.Button(row2, text="Delete Selected", command=self._delete_strategies).pack(side="left", expand=True,
                                                                                       fill="x", padx=1)

    def _refresh_tickers(self) -> None:
        """
        Fetches available tickers from the database and updates the dropdown.
        """

        tickers = get_existing_tickers()
        self.combo_ticker['values'] = tickers
        if tickers:
            self.combo_ticker.current(0)

    def _create_hybrid_row(
            self,
            parent: tk.Widget,
            row_idx: int,
            col_idx: int,
            label_text: str,
            var_amount: tk.DoubleVar,
            var_type: tk.StringVar,
            type_options: list[str]
            ) -> None:
        """
        Creates a labeled row with a value input and a unit dropdown.

        Args:
            parent (tk.Widget): The parent container.
            row_idx (int): Grid row index.
            col_idx (int): Grid column index.
            label_text (str): Label for the input.
            var_amount (tk.DoubleVar): Variable for the numeric input.
            var_type (tk.StringVar): Variable for the unit selection.
            type_options (list[str]): List of options for the unit dropdown.
        """

        ttk.Label(parent, text=label_text).grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky='w')
        container = ttk.Frame(parent)
        container.grid(row=row_idx, column=col_idx + 1, padx=5, pady=5, sticky='w')

        combo = ttk.Combobox(container, textvariable=var_type, values=type_options, state="readonly", width=8)
        combo.pack(side="left", padx=(0, 5))
        if not var_type.get(): combo.current(0)

        ttk.Entry(container, textvariable=var_amount, width=10).pack(side="left")

    def _toggle_hold(self) -> None:
        """
        Toggles the 'Max Holding' input between enabled and disabled (infinite).
        """

        if self.var_use_hold.get():
            if self.var_hold.get() == "∞":
                self.var_hold.set(self._last_hold_val)
            self.entry_hold.config(state='normal')
        else:
            current = self.var_hold.get()
            if current != "∞":
                self._last_hold_val = current
            self.var_hold.set("∞")
            self.entry_hold.config(state='disabled')

    def _toggle_threshold_inputs(
            self,
            parent_frame: tk.Widget,
            row: int,
            col: int
            ) -> None:
        """
        Switches between single-value threshold and range inputs.

        Args:
            parent_frame (tk.Widget): The parent container.
            row (int): Grid row index (unused in current logic, retained for signature compatibility).
            col (int): Grid column index (unused in current logic).
        """

        for widget in self.threshold_input_container.winfo_children():
            widget.destroy()

        if self.var_use_range.get():
            ttk.Entry(self.threshold_input_container, textvariable=self.var_thresh_min, width=8).pack(side="left")
            ttk.Label(self.threshold_input_container, text="↔").pack(side="left", padx=2)
            ttk.Entry(self.threshold_input_container, textvariable=self.var_thresh_max, width=8).pack(side="left")
        else:
            ttk.Entry(self.threshold_input_container, textvariable=self.var_threshold, width=15).pack(side="left")

    def _build_scrollable_target_list(
            self,
            parent_frame: tk.Widget,
            row_idx: int,
            col_idx: int
            ) -> None:
        """
        Constructs a scrollable area for adding multiple dynamic target prices.

        Used for MultiBoundedStrategy where users can define multiple static
        entry points or ranges.

        Args:
            parent_frame (tk.Widget): The parent container.
            row_idx (int): Grid row index.
            col_idx (int): Grid column index.
        """

        container = ttk.LabelFrame(parent_frame, text="Target Prices (Dynamic List)", padding=5)
        container.grid(row=row_idx, column=col_idx, columnspan=4, sticky='nsew', padx=5, pady=5)

        ctrl_frame = ttk.Frame(container)
        ctrl_frame.pack(side="top", fill="x", pady=(0, 5))

        ttk.Button(ctrl_frame, text="+ Add Target", command=self._add_target_row).pack(side="left")
        ttk.Label(ctrl_frame, text="(Values must be > 0)").pack(side="left", padx=10)

        canvas = tk.Canvas(container, height=150)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)

        self.scroll_target_frame = ttk.Frame(canvas)
        self.scroll_target_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        window_id = canvas.create_window((0, 0), window=self.scroll_target_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(window_id, width=e.width))

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.target_rows = []
        self._add_target_row()

    def _add_target_row(self) -> None:
        """
        Adds a new row for target input (value or range) to the scrollable list.
        """

        row_frame = ttk.Frame(self.scroll_target_frame)
        row_frame.pack(fill="x", pady=2, padx=2)

        var_range = tk.BooleanVar(value=False)
        var_v1 = tk.DoubleVar(value=0.0)
        var_v2 = tk.DoubleVar(value=0.0)

        input_container = ttk.Frame(row_frame)

        def render_inputs():
            for w in input_container.winfo_children():
                w.destroy()
            if var_range.get():
                ttk.Entry(input_container, textvariable=var_v1, width=8).pack(side="left")
                ttk.Label(input_container, text="↔").pack(side="left", padx=2)
                ttk.Entry(input_container, textvariable=var_v2, width=8).pack(side="left")
            else:
                ttk.Label(input_container, text="Target $ :").pack(side="left", padx=2)
                ttk.Entry(input_container, textvariable=var_v1, width=15).pack(side="left")

        chk = ttk.Checkbutton(row_frame, text="Range", variable=var_range, command=render_inputs)
        chk.pack(side="left", padx=5)

        input_container.pack(side="left", fill="x", expand=True)
        render_inputs()

        def delete_row():
            row_frame.destroy()
            row_data['deleted'] = True

        ttk.Button(row_frame, text="✖", width=3, command=delete_row).pack(side="right", padx=5)

        row_data = {
            'frame': row_frame,
            'var_range': var_range,
            'var_v1': var_v1,
            'var_v2': var_v2,
            'deleted': False
        }
        self.target_rows.append(row_data)

    def _on_type_changed(
            self,
            event: tk.Event | None
            ) -> None:
        """
        Updates the specific parameters UI when the strategy type changes.

        Dynamically destroys and rebuilds the specific_frame contents to match
        the requirements of the selected strategy (e.g., showing Stop Loss inputs
        for BoundedStrategy, or Trigger % for Dynamic strategies).

        Args:
            event (tk.Event | None): The triggering event (usually ComboboxSelected).
        """

        for widget in self.specific_frame.winfo_children():
            widget.destroy()

        strat_name = self.var_strat_type.get()
        grid_opts = {'padx': 5, 'pady': 5, 'sticky': 'w'}

        if strat_name == "Manual (Base)":
            self.manual_orders = []
            input_frame = ttk.Frame(self.specific_frame)
            input_frame.pack(fill="x", pady=5)

            ttk.Label(input_frame, text="Date:").pack(side="left", padx=5)
            self.entry_man_date = ttk.Entry(input_frame, width=10)
            self.entry_man_date.pack(side="left", padx=2)
            ttk.Label(input_frame, text="Type:").pack(side="left", padx=5)
            self.combo_man_type = ttk.Combobox(input_frame, values=self.ORDER_TYPES, state="readonly", width=8)
            self.combo_man_type.pack(side="left", padx=2)
            self.combo_man_type.current(0)
            ttk.Label(input_frame, text="Amt:").pack(side="left", padx=5)
            self.combo_man_sizing = ttk.Combobox(input_frame, values=self.SIZING_OPTIONS, state="readonly", width=10)
            self.combo_man_sizing.current(0)
            self.combo_man_sizing.pack(side="left", padx=2)
            self.entry_man_amount = ttk.Entry(input_frame, width=8)
            self.entry_man_amount.pack(side="left", padx=2)
            ttk.Button(input_frame, text="+", width=3, command=self._add_manual_order).pack(side="left", padx=5)

            cols = ("Date", "Type", "Sizing", "Amount")
            self.tree_orders = ttk.Treeview(self.specific_frame, columns=cols, show='headings', height=4)
            for col in cols:
                self.tree_orders.heading(col, text=col)
                self.tree_orders.column(col, width=80)
            self.tree_orders.pack(fill="x", padx=5, pady=5)

        else:
            r = 0
            if strat_name != "Bounded (SL/TP/Time)":
                self._create_hybrid_row(self.specific_frame, r, 0, "Amount per Trade:",
                                        self.var_amount, self.var_sizing_type, self.SIZING_OPTIONS)
                r += 1

            if "Bounded" in strat_name:
                hold_frame = ttk.Frame(self.specific_frame)
                hold_frame.grid(row=r, column=2, columnspan=2, **grid_opts)
                self.chk_hold = ttk.Checkbutton(hold_frame, text="Max Holding", variable=self.var_use_hold,
                                                command=self._toggle_hold)
                self.chk_hold.pack(side="left", padx=(0, 5))
                self.entry_hold = ttk.Entry(hold_frame, textvariable=self.var_hold, width=10)
                self.entry_hold.pack(side="left")
                self._toggle_hold()
                r += 1

                self._create_hybrid_row(self.specific_frame, r, 0, "Stop Loss:",
                                        self.var_sl, self.var_sl_type, self.PRICE_OPTIONS)
                self._create_hybrid_row(self.specific_frame, r, 2, "Take Profit:",
                                        self.var_tp, self.var_tp_type, self.PRICE_OPTIONS)
                r += 1

                if "Dynamic" in strat_name:
                    ttk.Label(self.specific_frame, text="Trigger %:").grid(row=r, column=0, **grid_opts)
                    ttk.Entry(self.specific_frame, textvariable=self.var_threshold).grid(row=r, column=1, **grid_opts)
                    ttk.Label(self.specific_frame, text="Lookback:").grid(row=r, column=2, **grid_opts)
                    ttk.Entry(self.specific_frame, textvariable=self.var_lookback).grid(row=r, column=3, **grid_opts)
                elif "Multi Bounded" == strat_name:
                    self._build_scrollable_target_list(self.specific_frame, r, 0)

            elif "Buy" in strat_name or "Sell" in strat_name:
                is_dynamic = "Dynamic" in strat_name
                lbl_thresh = "Trigger %:" if is_dynamic else "Trigger Price ($):"
                ttk.Label(self.specific_frame, text=lbl_thresh).grid(row=r, column=2, **grid_opts)
                thresh_complex_frame = ttk.Frame(self.specific_frame)
                thresh_complex_frame.grid(row=r, column=3, **grid_opts)
                self.chk_range = ttk.Checkbutton(thresh_complex_frame, text="Use Range", variable=self.var_use_range,
                                                 command=lambda: self._toggle_threshold_inputs(thresh_complex_frame, 0,
                                                                                               0))
                self.chk_range.pack(side="top", anchor='w')
                self.threshold_input_container = ttk.Frame(thresh_complex_frame)
                self.threshold_input_container.pack(side="top", anchor='w')
                self._toggle_threshold_inputs(thresh_complex_frame, 0, 0)
                if is_dynamic:
                    ttk.Label(self.specific_frame, text="Lookback:").grid(row=r + 1, column=0, **grid_opts)
                    ttk.Entry(self.specific_frame, textvariable=self.var_lookback).grid(row=r + 1, column=1,
                                                                                        **grid_opts)

    def _add_manual_order(self) -> None:
        """
        Captures input for a manual order and adds it to the list and UI tree.
        """

        dt = self.entry_man_date.get()
        typ = self.combo_man_type.get()
        sz = self.combo_man_sizing.get()
        amt = self.entry_man_amount.get()
        if dt and typ and amt:
            self.manual_orders.append({'date': dt, 'type': typ, 'sizing': sz, 'amount': float(amt)})
            self.tree_orders.insert("", "end", values=(dt, typ, sz, amt))

    def _map_sizing_to_backend(
            self,
            ui_sizing_val: str
            ) -> str:
        """
        Converts UI labels for position sizing to backend identifiers.

        Args:
            ui_sizing_val (str): The sizing type label from the UI.

        Returns:
            str: The backend identifier for the sizing type.
        """

        if ui_sizing_val == "$":
            return 'static'
        elif ui_sizing_val == "% Initial":
            return 'initial'
        elif ui_sizing_val == "% Current":
            return 'current'
        return 'static'

    def _get_threshold_value(self) -> float | tuple[float, float]:
        """
        Retrieves the threshold value, either as a single float or a range tuple.

        Returns:
            float | tuple[float, float]: The threshold value or range.
        """

        if self.var_use_range.get():
            v1 = self.var_thresh_min.get()
            v2 = self.var_thresh_max.get()
            return tuple(sorted((v1, v2)))
        else:
            return self.var_threshold.get()

    def _sanitize_sl_tp(self) -> tuple[float, float]:
        """
        Normalizes Stop Loss and Take Profit values.

        Ensures Stop Loss is negative and Take Profit is positive relative to the
        entry, correcting user input signs if necessary. Also handles percentage
        conversions (e.g., 5.0 becoming 0.05).

        Returns:
            tuple[float, float]: Validated (Stop Loss, Take Profit) values.
        """

        raw_sl = self.var_sl.get()
        raw_tp = self.var_tp.get()
        sl_type = self.var_sl_type.get()
        tp_type = self.var_tp_type.get()

        if sl_type == "%" and abs(raw_sl) >= 1.0:
            raw_sl /= 100.0
        if tp_type == "%" and abs(raw_tp) >= 1.0:
            raw_tp /= 100.0

        final_sl = -abs(raw_sl)
        final_tp = abs(raw_tp)

        return final_sl, final_tp

    def _create_strategy_dispatcher(self) -> None:
        """
        Validates inputs and dispatches strategy creation to the specific handler.

        Gathers common parameters (ticker, dates, capital) and calls the
        specific creation method based on the selected strategy type. Adds the
        resulting instance to the UI list.
        """

        try:
            ticker = self.var_ticker.get()
            start = self.var_start.get()
            end = self.var_end.get()
            capital = self.var_capital.get()
            name = self.var_name.get()
            strat_key = self.var_strat_type.get()

            sf = get_sf_from_sqlite(ticker, start=None, end=None)
            if sf.empty:
                messagebox.showerror("Error", f"No data found for ticker {ticker}.")
                return

            common_kwargs = {
                'ticker': ticker,
                'start': start,
                'end': end,
                'capital': capital,
                'sf': sf,
                'name': name
            }

            dispatch_map = {
                "Manual (Base)": self._create_manual_strategy,
                "Bounded (SL/TP/Time)": self._create_bounded_strategy,
                "Multi Bounded": self._create_multi_bounded_strategy,
                "Multi Dynamic Bounded": self._create_multi_dynamic_bounded_strategy,
                "Buy (Static Price)": self._create_buy_static_strategy,
                "Buy (Dynamic/Dip)": self._create_buy_dynamic_strategy,
                "Sell (Static Price)": self._create_sell_static_strategy,
                "Sell (Dynamic/Trailing)": self._create_sell_dynamic_strategy
            }

            creator_method = dispatch_map.get(strat_key)
            if creator_method:
                new_strategy = creator_method(common_kwargs)
                if new_strategy:
                    self._add_strategy_to_list(new_strategy, checked=False)
            else:
                messagebox.showerror("Error", "Unknown strategy type selected.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Creation Error", f"Failed to create strategy:\n{str(e)}")

    def _get_sizing_kwargs(self) -> dict[str, Any]:
        """
        Returns standard position sizing arguments from UI variables.

        Returns:
            dict[str, Any]: A dictionary containing amount per trade and sizing type.
        """

        return {
            'amount_per_trade': self.var_amount.get(),
            'sizing_type': self._map_sizing_to_backend(self.var_sizing_type.get())
        }

    def _create_manual_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> Strategy:
        """
        Constructs a basic Strategy with pre-defined manual orders.

        Sanitizes order dates by snapping them to the last valid market date
        if the requested date (e.g., Saturday) does not exist in the data.

        Args:
            common_kwargs (dict[str, Any]): Dictionary containing common
                strategy parameters (ticker, capital, dates, etc.).

        Returns:
            Strategy: An instance of the base Strategy class configured with
                the specified manual orders.
        """

        sf = common_kwargs['sf']
        sf.index = pd.to_datetime(sf.index).strftime('%Y-%m-%d')

        first_market_date = sf.index[0]

        processed_orders = []
        for order in self.manual_orders:

            target_date = order['date']
            original_date = target_date

            while target_date not in sf.index and target_date >= first_market_date:
                dt_obj = datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)
                target_date = dt_obj.strftime("%Y-%m-%d")

            final_date = target_date if target_date in sf.index else original_date

            processed_orders.append({
                'date': final_date,
                'type': order['type'],
                'amount': order['amount'],
                'override_sizing_type': self._map_sizing_to_backend(order['sizing'])
            })

        common_kwargs['manual_orders'] = processed_orders
        return Strategy(**common_kwargs)

    def _create_bounded_strategy(
            self,
            common_kwargs: dict[str, Any]
        ) -> BoundedStrategy:
        """
        Constructs a BoundedStrategy with SL, TP, and time limits.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            BoundedStrategy: The initialized bounded strategy.
        """

        kwargs = common_kwargs.copy()
        sl, tp = self._sanitize_sl_tp()
        kwargs['stop_loss'] = sl
        kwargs['take_profit'] = tp
        kwargs['max_holding_period'] = self.var_hold.get() if self.var_use_hold.get() else None
        kwargs['sl_type'] = self.var_sl_type.get()
        kwargs['tp_type'] = self.var_tp_type.get()
        return BoundedStrategy(**kwargs)

    def _create_multi_bounded_strategy(
            self,
            common_kwargs: dict[str, Any]
        ) -> MultiBoundedStrategy | None:
        """
        Constructs a MultiBoundedStrategy with multiple static targets.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            MultiBoundedStrategy | None: The initialized strategy, or None if no valid targets are defined.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())

        targets = []
        for row in self.target_rows:
            if row.get('deleted', False):
                continue
            is_range = row['var_range'].get()
            v1 = row['var_v1'].get()

            if is_range:
                v2 = row['var_v2'].get()
                if v1 > 0 or v2 > 0:
                    targets.append(tuple(sorted((v1, v2))))
            else:
                if v1 > 0:
                    targets.append(v1)

        print(f"DEBUG: Creating MultiBounded with Targets: {targets}")

        if not targets:
            messagebox.showwarning("Warning", "No valid targets (>0) defined.")
            return None

        kwargs['target_prices'] = targets
        sl, tp = self._sanitize_sl_tp()
        kwargs['stop_loss'] = sl
        kwargs['take_profit'] = tp
        kwargs['sl_type'] = self.var_sl_type.get()
        kwargs['tp_type'] = self.var_tp_type.get()
        kwargs['max_holding_period'] = self.var_hold.get() if self.var_use_hold.get() else None

        return MultiBoundedStrategy(**kwargs)

    def _create_multi_dynamic_bounded_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> MultiDynamicBoundedStrategy:
        """
        Constructs a MultiDynamicBoundedStrategy with momentum triggers.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            MultiDynamicBoundedStrategy: The initialized dynamic strategy.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())
        kwargs['trigger_pct'] = self.var_threshold.get()
        kwargs['trigger_lookback'] = self.var_lookback.get()
        sl, tp = self._sanitize_sl_tp()
        kwargs['stop_loss'] = sl
        kwargs['take_profit'] = tp
        kwargs['sl_type'] = self.var_sl_type.get()
        kwargs['tp_type'] = self.var_tp_type.get()
        kwargs['max_holding_period'] = self.var_hold.get() if self.var_use_hold.get() else None
        return MultiDynamicBoundedStrategy(**kwargs)

    def _create_buy_static_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> BuyStrategy:
        """
        Constructs a static BuyStrategy.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            BuyStrategy: The initialized static buy strategy.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())
        kwargs['threshold'] = self._get_threshold_value()
        return BuyStrategy(**kwargs)

    def _create_buy_dynamic_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> DynamicBuyStrategy:
        """
        Constructs a dynamic BuyStrategy.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            DynamicBuyStrategy: The initialized dynamic buy strategy.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())
        kwargs['threshold'] = self._get_threshold_value()
        kwargs['trigger_lookback'] = self.var_lookback.get()
        return DynamicBuyStrategy(**kwargs)

    def _create_sell_static_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> SellStrategy:
        """
        Constructs a static SellStrategy.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            SellStrategy: The initialized static sell strategy.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())
        kwargs['threshold'] = self._get_threshold_value()
        return SellStrategy(**kwargs)

    def _create_sell_dynamic_strategy(
            self,
            common_kwargs: dict[str, Any]
            ) -> DynamicSellStrategy:
        """
        Constructs a dynamic SellStrategy.

        Args:
            common_kwargs (dict[str, Any]): Common strategy parameters.

        Returns:
            DynamicSellStrategy: The initialized dynamic sell strategy.
        """

        kwargs = common_kwargs.copy()
        kwargs.update(self._get_sizing_kwargs())
        kwargs['threshold'] = self._get_threshold_value()
        kwargs['trigger_lookback'] = self.var_lookback.get()
        return DynamicSellStrategy(**kwargs)

    def _add_strategy_to_list(
            self,
            strategy_obj: Strategy,
            checked: bool = True
            ) -> None:
        """
        Registers a created strategy in the UI Treeview and internal list.

        Args:
            strategy_obj (Strategy): The instantiated strategy object.
            checked (bool): Initial selection state. Defaults to True.
        """

        strat_id = str(id(strategy_obj))
        check_symbol = "☑" if checked else "☐"
        ticker_val = getattr(strategy_obj, 'ticker', "Multi/Mix")
        self.created_strategies_data.append(
            {'id': strat_id, 'obj': strategy_obj, 'checked': checked, 'executed': False})
        self.tree_list.insert("", "end", iid=strat_id, values=(
        check_symbol, strategy_obj.name, type(strategy_obj).__name__, ticker_val, "📈", "📄"))
        self._update_execution_buttons()

    def _on_tree_click(
            self,
            event: tk.Event
            ) -> None:
        """
        Handles clicks on the strategy list to toggle selection or show stats.

        Detects which column was clicked:
        - Checkbox column: Toggles selection.
        - Perf column: Shows performance summary.
        - Ops column: Shows detailed operations log.

        Args:
            event (tk.Event): The click event.
        """

        region = self.tree_list.identify("region", event.x, event.y)
        if region == "cell":
            col = self.tree_list.identify_column(event.x)
            row_id = self.tree_list.identify_row(event.y)
            if not row_id: return
            if col == "#1":
                self._toggle_selection(row_id)
            elif col == "#5":
                self._show_performance(row_id)
            elif col == "#6":
                self._show_operations_window(row_id)

    def _toggle_selection(
            self,
            row_id: str
            ) -> None:
        """
        Toggles the check state of a strategy in the list.

        Args:
            row_id (str): The ID of the row to toggle.
        """

        for item in self.created_strategies_data:
            if item['id'] == row_id:
                item['checked'] = not item['checked']
                new_sym = "☑" if item['checked'] else "☐"
                current_values = self.tree_list.item(row_id, "values")
                self.tree_list.item(row_id, values=(new_sym, *current_values[1:]))
                break
        self._update_execution_buttons()

    def _update_execution_buttons(self) -> None:
        """
        Enables or disables execution buttons based on current selection.
        """

        selected_items = [item for item in self.created_strategies_data if item['checked']]
        if not selected_items:
            self.btn_exec.config(state="disabled")
            self.btn_exec_save.config(state="disabled")
            return
        already_executed = any(item['executed'] for item in selected_items)
        if already_executed:
            self.btn_exec.config(state="disabled")
            self.btn_exec_save.config(state="disabled")
        else:
            self.btn_exec.config(state="normal")
            self.btn_exec_save.config(state="normal")

    def _reset_strategy_state(
            self,
            strategy_obj: Strategy
            ) -> None:
        """
        Resets the runtime state of a strategy to allow re-execution.

        Recursively cleans up operations, profits, closed flags, and resets capital.
        Special handling is applied for MultiStrategies and BoundedStrategies to
        reset children and trigger initial entries.

        Args:
            strategy_obj (Strategy): The strategy instance to reset.
        """

        is_multi = isinstance(strategy_obj, MultiStrategy)

        if hasattr(strategy_obj, 'fiat'):
            if is_multi:
                strategy_obj.fiat = 0.0
            else:
                strategy_obj.fiat = strategy_obj.initial_capital

        if hasattr(strategy_obj, 'stock'):
            strategy_obj.stock = 0.0

        if hasattr(strategy_obj, 'closed'):
            strategy_obj.closed = False

        if hasattr(strategy_obj, 'operations'):
            strategy_obj.operations = []

        if hasattr(strategy_obj, 'profits'):
            strategy_obj.profits = None

        if hasattr(strategy_obj, '_executed_manual_orders'):
            strategy_obj._executed_manual_orders = set()

        if hasattr(strategy_obj, 'finished_strategies'):
            if hasattr(strategy_obj, 'active_strategies'):
                strategy_obj.active_strategies.extend(strategy_obj.finished_strategies)
            strategy_obj.finished_strategies = []

        if hasattr(strategy_obj, 'active_strategies'):
            for child in strategy_obj.active_strategies:
                self._reset_strategy_state(child)

        if isinstance(strategy_obj, (MultiBoundedStrategy, MultiDynamicBoundedStrategy)):
            strategy_obj.active_strategies = []
            strategy_obj.finished_strategies = []
            strategy_obj.triggered_targets = set()

        if isinstance(strategy_obj, (BoundedStrategy, SellStrategy)):
            strategy_obj.buy_all(strategy_obj.start, trigger="reset_entry")

    def _sum_strategies(self) -> None:
        """
        Combines selected strategies into a new MultiStrategy using operator overloading.

        Deep copies the selected instances to prevent modifying the originals.
        Prompts the user for a new name for the combined strategy.
        """

        selected_strategies = [item['obj'] for item in self.created_strategies_data if item['checked']]

        if len(selected_strategies) < 2:
            messagebox.showwarning("Warning", "Select at least 2 strategies to sum.")
            return

        new_name = simpledialog.askstring("Strategy Name", "Enter a name for the combined MultiStrategy:")
        if not new_name: return

        try:
            cloned_strategies = [copy.deepcopy(s) for s in selected_strategies]

            for s in cloned_strategies:
                self._reset_strategy_state(s)

            combined_strat = cloned_strategies[0]
            for s in cloned_strategies[1:]:
                combined_strat = combined_strat + s

            combined_strat.name = new_name

            self._reset_strategy_state(combined_strat)

            self._add_strategy_to_list(combined_strat, checked=False)
            messagebox.showinfo("Success", f"Created combined strategy: {new_name}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Sum Error", f"Could not sum strategies:\n{e}")

    def _delete_strategies(self) -> None:
        """
        Removes selected strategies from the UI list and internal storage.
        """

        to_remove = [item['id'] for item in self.created_strategies_data if item['checked']]
        if not to_remove: return
        for rid in to_remove:
            self.tree_list.delete(rid)
        self.created_strategies_data = [item for item in self.created_strategies_data if item['id'] not in to_remove]
        self._update_execution_buttons()

    def _execute_selected(
            self,
            save: bool = False
            ) -> None:
        """
        Executes the selected strategies.

        Iterates through checked strategies, resets their state, runs the
        simulation (optionally saving to DB), and updates the UI with the
        results summary (Success/Total Operations).

        Args:
            save (bool): If True, saves results to 'data/strategies_results.db'.
        """

        selected_items = [item for item in self.created_strategies_data if item['checked']]

        if any(item['executed'] for item in selected_items):
            messagebox.showwarning("Blocked", "One or more selected strategies have already been executed.")
            return

        if not selected_items:
            messagebox.showwarning("Warning", "No strategies selected to execute.")
            return

        executed_count = 0
        try:
            default_db_path = "data/strategies_results.db"

            for item in selected_items:
                strat = item['obj']
                self._reset_strategy_state(strat)

                if save:
                    strat.execute_and_save(db_route=default_db_path)
                else:
                    strat.execute()

                item['executed'] = True

                all_ops = self._collect_all_operations(strat)

                successful_ops = [op for op in all_ops if op.successful]

                n_total = len(all_ops)
                n_success = len(successful_ops)

                ops_display = f"{n_success} ({n_total})" if n_total != n_success else f"{n_success}"

                current_values = self.tree_list.item(item['id'], "values")
                self.tree_list.item(
                    item['id'],
                    values=(
                        current_values[0],
                        current_values[1],
                        current_values[2],
                        current_values[3],
                        "✅",
                        ops_display
                    )
                )
                executed_count += 1

            self._update_execution_buttons()
            action_lbl = "Executed & Saved" if save else "Executed"
            messagebox.showinfo("Execution", f"{action_lbl} {executed_count} strategies.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Execution Error", f"Error during execution:\n{e}")

    def _get_strat_by_id(
            self,
            row_id: str
            ) -> Strategy | None:
        """
        Retrieves a strategy object from internal storage by its unique ID.

        Args:
            row_id (str): The unique identifier of the strategy row.

        Returns:
            Strategy | None: The strategy object if found, else None.
        """

        for item in self.created_strategies_data:
            if item['id'] == row_id: return item['obj']
        return None

    def _collect_all_operations(
            self,
            strat: Strategy,
            visited: set[int] | None = None
            ) -> list[Any]:
        """
        Recursively collects operations from a strategy and its nested children.

        Uses a visited set to prevent infinite loops in cyclic references,
        though strategy structures should typically be acyclic trees.

        Args:
            strat (Strategy): The strategy instance to inspect.
            visited (set[int] | None): Set of visited object IDs.

        Returns:
            list[Any]: A flattened list of all Operation objects found.
        """

        if visited is None:
            visited = set()

        if id(strat) in visited:
            return []
        visited.add(id(strat))

        ops = []

        if hasattr(strat, 'operations'):
            ops.extend(strat.operations)

        if hasattr(strat, 'active_strategies'):
            for child in strat.active_strategies:
                ops.extend(self._collect_all_operations(child, visited))

        if hasattr(strat, 'finished_strategies'):
            for child in strat.finished_strategies:
                ops.extend(self._collect_all_operations(child, visited))

        return ops

    def _show_performance(
            self,
            row_id: str
            ) -> None:
        """
        Displays a popup with the performance summary of the selected strategy.

        Args:
            row_id (str): The unique identifier of the strategy row.
        """

        strat = self._get_strat_by_id(row_id)
        if not strat: return
        all_ops = self._collect_all_operations(strat)
        if not all_ops:
            messagebox.showinfo("Performance", f"Strategy '{strat.name}' has no trades yet.\nDid you execute it?")
            return
        n_trades = len(all_ops)
        final_cap = getattr(strat, 'fiat', 0.0)
        profit = getattr(strat, 'profits', 0.0) if strat.profits is not None else "N/A"
        msg = f"Strategy: {strat.name}\nType: {type(strat).__name__}\n" + "-" * 30 + f"\nTotal Ops: {n_trades}\nFinal Capital (Fiat): {final_cap:.2f}\nRealized Profit: {profit}\n"
        messagebox.showinfo("Performance Summary", msg)

    def _show_operations_window(
            self,
            row_id: str
            ) -> None:
        """
        Opens a detailed window showing the log of all operations.

        Args:
            row_id (str): The unique identifier of the strategy row.
        """

        strat = self._get_strat_by_id(row_id)
        if not strat: return
        all_ops = self._collect_all_operations(strat)
        all_ops.sort(key=lambda x: x.date)
        if not all_ops:
            messagebox.showinfo("Operations", "No operations to show.")
            return
        top = tk.Toplevel(self)
        top.title(f"Operations: {strat.name}")
        top.geometry("700x500")
        ctrl_frame = ttk.Frame(top, padding=5)
        ctrl_frame.pack(side="top", fill="x")
        var_table_view = tk.BooleanVar(value=True)
        content_frame = ttk.Frame(top)
        content_frame.pack(side="top", fill="both", expand=True)

        def render_view():
            for widget in content_frame.winfo_children(): widget.destroy()
            if var_table_view.get():
                cols = ("Date", "Type", "Ticker", "Price", "Cash Amt", "Success")
                tree = ttk.Treeview(content_frame, columns=cols, show="headings")
                for c in cols: tree.heading(c, text=c); tree.column(c, width=100)
                vsb = ttk.Scrollbar(content_frame, orient="vertical", command=tree.yview)
                tree.configure(yscroll=vsb.set)
                tree.pack(side="left", fill="both", expand=True);
                vsb.pack(side="right", fill="y")
                for op in all_ops:
                    tree.insert("", "end", values=(
                    op.date, op.type, op.ticker, f"{op.stock_price:.2f}", f"{op.cash_amount:.2f}",
                    "Yes" if op.successful else "No"))
            else:
                txt = scrolledtext.ScrolledText(content_frame, width=90, height=20)
                txt.pack(fill="both", expand=True)
                for i, op in enumerate(all_ops): txt.insert("end", f"#{i + 1}: {op.get_description()}\n{'-' * 50}\n")
                txt.config(state="disabled")

        chk = ttk.Checkbutton(ctrl_frame, text="Table View / Text View", variable=var_table_view, command=render_view)
        chk.pack(side="left", padx=10)
        render_view()