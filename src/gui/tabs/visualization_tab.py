"""Visualization interface for displaying historical price and strategy charts.

This module defines the `VisualizationTab` class, which embeds a Matplotlib figure
within the Tkinter interface. It allows users to select a ticker from the
local database (Market or Strategy data), select specific data columns, and
construct a custom plot with multiple series.
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
    Provides controls to load datasets into memory, select specific columns
    from those datasets, and manage a list of traces (series) to be plotted together.

    Attributes:
        ticker_var (tk.StringVar): Variable holding the currently selected ticker.
        combo_ticker (ttk.Combobox): Dropdown menu for ticker selection.
        fig (plt.Figure): The Matplotlib figure object.
        ax (plt.Axes): The axes object where the plot is drawn.
        canvas (FigureCanvasTkAgg): The canvas widget embedding the plot in Tkinter.
        source_var (tk.StringVar): Variable selecting the data source (Market or Strategy).
        list_columns (tk.Listbox): Listbox for selecting a single column to add.
        lst_loaded (tk.Listbox): Listbox displaying datasets currently in memory.
        lst_plottables (tk.Listbox): Listbox displaying the list of series to plot.
        loaded_datasets (dict[str, pd.DataFrame]): Dictionary storing the dataframes of added datasets.
        plottable_series (list[tuple[str, str]]): List of (dataset_key, column_name) tuples to be plotted.
    """

    def __init__(
            self,
            parent: ttk.Notebook
            ) -> None:
        """Initializes the visualization tab UI components and plotting backend.

        Sets up the control panel with three main sections (Datasets, Columns, Plottables)
        and the graph area containing the Matplotlib canvas and toolbar.

        Args:
            parent (ttk.Notebook): The parent widget to which this frame belongs.
        """

        super().__init__(parent)
        
        self.top_panel = ttk.Frame(self)
        self.top_panel.pack(side="top", fill="x", padx=10, pady=(10, 5))
        
        ttk.Label(self.top_panel, text="Source:").pack(side="left", padx=(0, 5))
        self.source_var = tk.StringVar(value="Market Data")
        self.combo_source = ttk.Combobox(self.top_panel, textvariable=self.source_var, 
                                         values=["Market Data", "Strategy Data"], state="readonly", width=12)
        self.combo_source.pack(side="left", padx=(0, 10))
        self.combo_source.bind("<<ComboboxSelected>>", lambda e: self.refresh_ticker_list())

        ttk.Label(self.top_panel, text="Ticker:").pack(side="left", padx=(0, 5))
        self.ticker_var = tk.StringVar()
        self.combo_ticker = ttk.Combobox(self.top_panel, textvariable=self.ticker_var, width=15)
        self.combo_ticker.pack(side="left", padx=(0, 5))
        
        self.btn_refresh = ttk.Button(self.top_panel, text="↻", width=3, command=self.refresh_ticker_list)
        self.btn_refresh.pack(side="left", padx=(0, 10))
        
        self.btn_load = ttk.Button(self.top_panel, text="Load Dataset", command=self.on_load_click)
        self.btn_load.pack(side="left", padx=(0, 10))

        self.lbl_status = ttk.Label(self.top_panel, text="Ready.", foreground="gray")
        self.lbl_status.pack(side="left", padx=10)

        self.mid_panel = ttk.Frame(self)
        self.mid_panel.pack(side="top", fill="x", padx=10, pady=5)
        
        frame_loaded = ttk.LabelFrame(self.mid_panel, text="1. Loaded Datasets")
        frame_loaded.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.lst_loaded = tk.Listbox(frame_loaded, height=5, exportselection=False)
        self.lst_loaded.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        self.lst_loaded.bind('<<ListboxSelect>>', self._on_dataset_select)

        frame_cols = ttk.LabelFrame(self.mid_panel, text="2. Select Column")
        frame_cols.pack(side="left", fill="both", expand=True, padx=5)
        
        self.list_columns = tk.Listbox(frame_cols, selectmode="browse", height=4, exportselection=False)
        self.list_columns.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        self.btn_add_trace = ttk.Button(frame_cols, text="Add Trace ->", command=self._add_trace)
        self.btn_add_trace.pack(side="bottom", fill="x", padx=5, pady=5)

        frame_plot = ttk.LabelFrame(self.mid_panel, text="3. Traces to Plot")
        frame_plot.pack(side="left", fill="both", expand=True, padx=(5, 0))
        
        self.lst_plottables = tk.Listbox(frame_plot, height=4, selectmode="extended", exportselection=False)
        self.lst_plottables.pack(side="top", fill="both", expand=True, padx=5, pady=5)
        
        btn_frame_plot_actions = ttk.Frame(frame_plot)
        btn_frame_plot_actions.pack(side="bottom", fill="x", padx=5, pady=5)
        
        self.btn_remove_trace = ttk.Button(btn_frame_plot_actions, text="Remove Selected", command=self._remove_trace)
        self.btn_remove_trace.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.btn_plot = ttk.Button(btn_frame_plot_actions, text="PLOT GRAPH", command=self._plot_traces)
        self.btn_plot.pack(side="left", fill="x", expand=True, padx=(2, 0))

        self.graph_frame = ttk.Frame(self, relief="sunken", borderwidth=1)
        self.graph_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.fig, self.ax = plt.subplots(figsize=(5, 4), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0') 

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.graph_frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.loaded_datasets: dict[str, pd.DataFrame] = {} 
        self.plottable_series: list[tuple[str, str]] = [] 
        
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

    def on_load_click(self) -> None:
        """Handles the click event for the 'Load Dataset' button.

        Validates the selected ticker and initiates the data loading process
        (`_load_db_data`) in a separate daemon thread.
        """

        ticker = self.ticker_var.get().strip()
        if not ticker: return
        
        source = self.source_var.get()
        db_path = 'data/market_data.db' if source == "Market Data" else 'data/strategies_results.db'

        self.lbl_status.config(text=f"Reading {ticker}...", foreground="black")
        
        thread = threading.Thread(target=self._load_db_data, args=(ticker, source, db_path), daemon=True)
        thread.start()

    def _load_db_data(
            self,
            ticker: str,
            source: str,
            db_path: str
            ) -> None:
        """Fetches historical data for the specified ticker from the database.

        Intended to run in a separate thread. Retrieves the DataFrame
        via `src.database.get_sf_from_sqlite`.

        Args:
            ticker (str): The symbol of the asset to load.
            source (str): The origin of the data (Market or Strategy).
            db_path (str): The path to the database.
        """

        try:
            sf = get_sf_from_sqlite(ticker, db_path=db_path)
            self.after(0, self._data_loaded_callback, ticker, source, sf)
        except Exception as e:
            self.after(0, self._handle_error, str(e))

    def _data_loaded_callback(
            self,
            ticker: str,
            source: str,
            df: pd.DataFrame
            ) -> None:
        """Callback executed when data is successfully loaded.

        Stores the DataFrame, updates the 'Loaded Datasets' listbox, and
        automatically selects the new dataset to trigger column updates.

        Args:
            ticker (str): The symbol of the loaded asset.
            source (str): The origin of the data.
            df (pd.DataFrame): The dataframe containing historical data.
        """
        
        if df.empty:
            messagebox.showwarning("Not Found", f"Data '{ticker}' not found or empty.")
            self.lbl_status.config(text="Data not found.", foreground="orange")
            return

        key = f"{ticker} ({source})"
        self.loaded_datasets[key] = df
        
        all_items = self.lst_loaded.get(0, tk.END)
        if key not in all_items:
            self.lst_loaded.insert(tk.END, key)
            
        self.lbl_status.config(text=f"Loaded {ticker}.", foreground="green")

        try:
            idx = self.lst_loaded.get(0, tk.END).index(key)
            self.lst_loaded.selection_clear(0, tk.END)
            self.lst_loaded.selection_set(idx)
            self.lst_loaded.activate(idx)
            self._on_dataset_select(None)
        except ValueError:
            pass

    def _on_dataset_select(
            self, 
            event: tk.Event | None
            ) -> None:
        """Updates the columns listbox when a dataset is selected.

        Retrieves the selected dataset key from `lst_loaded`, finds the
        corresponding DataFrame, and populates `list_columns`.

        Args:
            event (tk.Event | None): The triggering event.
        """

        selection = self.lst_loaded.curselection()
        if not selection:
            return

        key = self.lst_loaded.get(selection[0])
        df = self.loaded_datasets.get(key)
        
        if df is not None:
            self.list_columns.delete(0, tk.END)
            for col in df.columns:
                self.list_columns.insert(tk.END, col)
            
            default_cols = ['Close', 'Total_Equity']
            for i, col in enumerate(df.columns):
                if col in default_cols:
                    self.list_columns.selection_set(i)
                    break

    def _add_trace(self) -> None:
        """Adds the selected column from the current dataset to the plot list.

        Identifies the selected dataset and the selected column, creates a
        reference tuple, and adds it to `plottable_series` and `lst_plottables`.
        """
        
        ds_selection = self.lst_loaded.curselection()
        col_selection = self.list_columns.curselection()

        if not ds_selection:
            messagebox.showwarning("Selection Error", "Please select a dataset first.")
            return
        
        if not col_selection:
            messagebox.showwarning("Selection Error", "Please select a column to plot.")
            return

        ds_key = self.lst_loaded.get(ds_selection[0])
        col_name = self.list_columns.get(col_selection[0])
        
        trace_entry = (ds_key, col_name)
        display_str = f"{ds_key} - [{col_name}]"

        current_list = self.lst_plottables.get(0, tk.END)
        if display_str in current_list:
             return

        self.plottable_series.append(trace_entry)
        self.lst_plottables.insert(tk.END, display_str)

    def _remove_trace(self) -> None:
        """Removes selected items from the list of traces to plot.

        Iterates backwards through selected indices to remove items correctly
        from both the UI listbox and the internal `plottable_series` list.
        """

        selection = list(self.lst_plottables.curselection())
        if not selection:
            return
        
        selection.sort(reverse=True)
        
        for idx in selection:
            self.lst_plottables.delete(idx)
            if idx < len(self.plottable_series):
                self.plottable_series.pop(idx)

    def _plot_traces(self) -> None:
        """Renders the graph with all series currently in the plot list.

        Iterates through `plottable_series`, retrieves the data from
        `loaded_datasets`, and plots each as a line series on the Matplotlib axes.
        """

        self.ax.clear()
        
        if not self.plottable_series:
            self.ax.text(0.5, 0.5, "No traces added to plot.", ha='center')
            self.canvas.draw()
            return

        for ds_key, col_name in self.plottable_series:
            df = self.loaded_datasets.get(ds_key)
            if df is not None and col_name in df.columns:
                df_plot = df.copy()
                df_plot.index = pd.to_datetime(df_plot.index)
                
                label = f"{ds_key} [{col_name}]"
                self.ax.plot(df_plot.index, df_plot[col_name], label=label)
            else:
                print(f"Warning: Could not plot {ds_key} - {col_name}")

        self.ax.legend()
        self.ax.set_title("Multi-Series Analysis")
        self.ax.grid(True, linestyle='--', alpha=0.5)
        
        self.fig.autofmt_xdate()
        
        self.canvas.draw()

    def _handle_error(
            self,
            msg: str
            ) -> None:
        """Displays an error message to the user safely from the UI thread.

        Args:
            msg (str): The error description.
        """
        
        self.lbl_status.config(text="Error.", foreground="red")
        messagebox.showerror("Database Error", msg)