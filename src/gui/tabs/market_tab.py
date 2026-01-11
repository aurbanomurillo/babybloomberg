"""Visualization interface for displaying historical price and strategy charts.

This module defines the `VisualizationTab` class, which embeds a Matplotlib figure
within the Tkinter interface. It allows users to select a ticker from the
local database (Market or Strategy data) and view its history.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import mplfinance as mpf
from src.stockframe_manager import StockFrame
from src.database import get_sf_from_sqlite, get_existing_tickers

class VisualizationTab(ttk.Frame):
    """A GUI tab for visualizing stock market and strategy data using interactive charts.

    Integrates `matplotlib` and `mplfinance` to render financial charts.
    Provides controls to select a data source (Market/Strategy), a ticker,
    choose specific columns to plot, and toggle chart types.

    Attributes:
        ticker_var (tk.StringVar): Variable holding the currently selected ticker.
        combo_ticker (ttk.Combobox): Dropdown menu for ticker selection.
        var_candles (tk.BooleanVar): State of the candlestick toggle checkbox.
        fig (plt.Figure): The Matplotlib figure object.
        ax (plt.Axes): The axes object where the plot is drawn.
        canvas (FigureCanvasTkAgg): The canvas widget embedding the plot in Tkinter.
        source_var (tk.StringVar): Variable selecting the data source (Market or Strategy).
        list_columns (tk.Listbox): Listbox for selecting columns to plot.
    """

    def __init__(
            self,
            parent: ttk.Notebook
            ) -> None:
        """Initializes the visualization tab UI components and plotting backend.

        Sets up the control panel (dropdowns, buttons) and the graph area
        containing the Matplotlib canvas and toolbar.

        Args:
            parent (ttk.Notebook): The parent widget to which this frame belongs.
        """

        super().__init__(parent)
        
        self.control_frame: ttk.Frame = ttk.Frame(self)
        self.control_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        ttk.Label(self.control_frame, text="Source:").pack(side="left", padx=(0, 5))
        self.source_var = tk.StringVar(value="Market Data")
        self.combo_source = ttk.Combobox(self.control_frame, textvariable=self.source_var, 
                                         values=["Market Data", "Strategy Data"], state="readonly", width=12)
        self.combo_source.pack(side="left", padx=(0, 10))
        self.combo_source.bind("<<ComboboxSelected>>", lambda e: self.refresh_ticker_list())

        self.lbl_ticker: ttk.Label = ttk.Label(self.control_frame, text="Select Data:")
        self.lbl_ticker.pack(side="left", padx=(0, 5))
        
        self.ticker_var: tk.StringVar = tk.StringVar()
        self.combo_ticker: ttk.Combobox = ttk.Combobox(self.control_frame, textvariable=self.ticker_var, width=20)
        self.combo_ticker.pack(side="left", padx=(0, 5))
        self.combo_ticker.bind('<Return>', lambda event: self.on_view_click())
        
        self.btn_refresh: ttk.Button = ttk.Button(self.control_frame, text="↻", width=3, command=self.refresh_ticker_list)
        self.btn_refresh.pack(side="left", padx=(0, 15))
        
        self.btn_view: ttk.Button = ttk.Button(self.control_frame, text="Load Data", command=self.on_view_click)
        self.btn_view.pack(side="left", padx=(0, 10))

        col_frame = ttk.LabelFrame(self.control_frame, text="Select Columns")
        col_frame.pack(side="left", padx=10, fill="y")
        
        self.list_columns = tk.Listbox(col_frame, selectmode="multiple", height=3, width=15, exportselection=False)
        self.list_columns.pack(side="left", fill="y")
        self.list_columns.bind('<<ListboxSelect>>', self._on_col_select)
        
        self.btn_redraw: ttk.Button = ttk.Button(col_frame, text="Plot", command=self._plot_current_data)
        self.btn_redraw.pack(side="left", padx=2)

        self.var_candles: tk.BooleanVar = tk.BooleanVar(value=True)
        self.chk_candles: ttk.Checkbutton = ttk.Checkbutton(self.control_frame, text="Candles (OHLC)", variable=self.var_candles)
        self.chk_candles.pack(side="left", padx=(10, 0))

        self.lbl_status:ttk.Label = ttk.Label(self.control_frame, text="Ready.", foreground="gray")
        self.lbl_status.pack(side="left", padx=10)

        self.graph_frame:ttk.Frame = ttk.Frame(self, relief="sunken", borderwidth=1)
        self.graph_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.fig, self.ax = plt.subplots(figsize=(5, 4), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0') 

        self.canvas: FigureCanvasTkAgg = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.toolbar: NavigationToolbar2Tk = NavigationToolbar2Tk(self.canvas, self.graph_frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.current_df = pd.DataFrame() 
        self.refresh_ticker_list()

    def refresh_ticker_list(self) -> None:
        """Fetches the list of available tickers from the selected database and updates the UI.

        Queries `src.database.get_existing_tickers` using the appropriate DB path.
        """
        
        source = self.source_var.get()
        db_path = 'data/market_data.db' if source == "Market Data" else 'data/strategies_results.db'
        
        tickers = get_existing_tickers(db_path=db_path)
        self.combo_ticker['values'] = tickers
        if tickers:
            self.combo_ticker.current(0)
        self.ticker_var.set(tickers[0] if tickers else "")

    def on_view_click(self) -> None:
        """Handles the click event for the 'Load Data' button.

        Validates the selected ticker and initiates the data loading process
        (`_load_db_data`) in a separate daemon thread to prevent UI freezing.
        """

        ticker = self.ticker_var.get().strip()
        if not ticker: return
        
        source = self.source_var.get()
        db_path = 'data/market_data.db' if source == "Market Data" else 'data/strategies_results.db'

        self.lbl_status.config(text=f"Reading {ticker}...", foreground="black")
        
        thread = threading.Thread(target=self._load_db_data, args=(ticker, db_path), daemon=True)
        thread.start()

    def _load_db_data(
            self,
            ticker: str,
            db_path: str
            ) -> None:
        """Fetches historical data for the specified ticker from the database.

        Intended to run in a separate thread. Retrieves the DataFrame
        via `src.database.get_sf_from_sqlite` and schedules the UI update.

        Args:
            ticker (str): The symbol of the asset to load.
            db_path (str): The path to the database.
        """

        try:
            sf = get_sf_from_sqlite(ticker, db_path=db_path)
            self.after(0, self._data_loaded_callback, ticker, sf)
        except Exception as e:
            self.after(0, self._handle_error, str(e))

    def _data_loaded_callback(
            self,
            ticker: str,
            df: pd.DataFrame
            ) -> None:
        """Callback executed when data is successfully loaded.

        Updates the internal dataframe reference, populates the column listbox,
        and triggers an initial default plot.
        """
        
        self.current_df = df
        self.lbl_status.config(text=f"Loaded {ticker} ({len(df)} records).", foreground="green")

        if df.empty:
            messagebox.showwarning("Not Found", f"Data '{ticker}' not found or empty.")
            return

        self.list_columns.delete(0, tk.END)
        cols = list(df.columns)
        for c in cols:
            self.list_columns.insert(tk.END, c)

        default_cols = ['Close', 'Total_Equity']
        for i, c in enumerate(cols):
            if c in default_cols:
                self.list_columns.selection_set(i)

        self._plot_current_data()

    def _on_col_select(
            self, 
            event: tk.Event
            ) -> None:
        """Handles listbox selection changes."""
        pass 

    def _plot_current_data(self) -> None:
        """Renders the chart based on selected columns and settings.

        If "Candles" is checked and valid OHLC data exists, plots candles.
        Otherwise, plots the selected columns as a line chart.
        """

        if self.current_df.empty: return

        df_plot = self.current_df.copy()
        df_plot.index = pd.to_datetime(df_plot.index)

        self.ax.clear()
        
        is_market = self.source_var.get() == "Market Data"
        has_ohlc = all(col in df_plot.columns for col in ['Open', 'High', 'Low', 'Close'])
        
        selected_indices = self.list_columns.curselection()
        selected_cols = [self.list_columns.get(i) for i in selected_indices]

        if self.var_candles.get() and is_market and has_ohlc and (not selected_cols or 'Close' in selected_cols):
            try:
                mpf.plot(
                    df_plot, 
                    type='candle',
                    style='yahoo', 
                    ax=self.ax, 
                    volume=False, 
                    show_nontrading=False,
                    warn_too_much_data=1000000 
                )
                self.ax.set_title(f"{self.ticker_var.get()} (Candles)")
            except Exception as e:
                self.ax.text(0.5, 0.5, f"Plot Error: {e}", ha='center')
        else:
            if not selected_cols:
                self.ax.text(0.5, 0.5, "No columns selected.", ha='center')
            else:
                for col in selected_cols:
                    if col in df_plot.columns:
                        self.ax.plot(df_plot.index, df_plot[col], label=col)
                self.ax.legend()
                self.ax.set_title(f"{self.ticker_var.get()}")

        self.ax.grid(True, linestyle='--', alpha=0.5)
        self.canvas.draw()

    def _handle_error(
            self,
            msg: str
            ) -> None:
        """Displays an error message to the user safely from the UI thread."""
        
        self.lbl_status.config(text="Error.", foreground="red")
        messagebox.showerror("Database Error", msg)