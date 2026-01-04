import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import mplfinance as mpf
from src.stockframe_manager import StockFrame
from src.database import get_sf_from_sqlite, get_existing_tickers

class MarketTab(ttk.Frame):

    def __init__(
            self,
            parent: ttk.Notebook
            ):
        
        super().__init__(parent)
        
        self.control_frame: ttk.Frame = ttk.Frame(self)
        self.control_frame.pack(side="top", fill="x", padx=10, pady=10)
        
        self.lbl_ticker: ttk.Label = ttk.Label(self.control_frame, text="Select Ticker:")
        self.lbl_ticker.pack(side="left", padx=(0, 5))
        
        self.ticker_var: tk.StringVar = tk.StringVar()
        self.combo_ticker: ttk.Combobox = ttk.Combobox(self.control_frame, textvariable=self.ticker_var, width=15)
        self.combo_ticker.pack(side="left", padx=(0, 5))
        self.combo_ticker.bind('<Return>', lambda event: self.on_view_click())
        
        self.btn_refresh: ttk.Button = ttk.Button(self.control_frame, text="↻", width=3, command=self.refresh_ticker_list)
        self.btn_refresh.pack(side="left", padx=(0, 15))
        
        self.var_candles: tk.BooleanVar = tk.BooleanVar(value=True) # Marcado por defecto
        self.chk_candles: ttk.Checkbutton = ttk.Checkbutton(self.control_frame, text="Candlesticks", variable=self.var_candles)
        self.chk_candles.pack(side="left", padx=(0, 10))

        self.btn_view: ttk.Button = ttk.Button(self.control_frame, text="Visualize", command=self.on_view_click)
        self.btn_view.pack(side="left")

        self.lbl_status:ttk.Label = ttk.Label(self.control_frame, text="Ready.", foreground="gray")
        self.lbl_status.pack(side="left", padx=10)

        self.refresh_ticker_list()

        self.graph_frame:ttk.Frame = ttk.Frame(self, relief="sunken", borderwidth=1)
        self.graph_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.fig, self.ax = plt.subplots(figsize=(5, 4), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0') 

        self.canvas: FigureCanvasTkAgg = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.toolbar: NavigationToolbar2Tk = NavigationToolbar2Tk(self.canvas, self.graph_frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def refresh_ticker_list(self) -> None:
        tickers = get_existing_tickers()
        self.combo_ticker['values'] = tickers
        if tickers:
            self.combo_ticker.current(0) 

    def on_view_click(self) -> None:
        ticker = self.ticker_var.get().upper().strip()
        if not ticker: return
        
        self.lbl_status.config(text=f"Reading {ticker} from DB...", foreground="black")
        
        thread = threading.Thread(target=self._load_db_data, args=(ticker,), daemon=True)
        thread.start()

    def _load_db_data(
            self,
            ticker: str
            ) -> None:
        
        try:
            sf = get_sf_from_sqlite(ticker)
            self.after(0, self._update_chart_ui, ticker, sf)
        except Exception as e:
            self.after(0, self._handle_error, str(e))

    def _update_chart_ui(
            self,
            ticker: str,
            sf: StockFrame
            ):
        
        self.lbl_status.config(text=f"Loaded {ticker} ({len(sf)} records).", foreground="green")

        if sf.empty:
            messagebox.showwarning("Not Found", f"Ticker '{ticker}' not found in Database.\nPlease go to 'Download Data' tab first.")
            return

        sf_plot = sf.copy()
        sf_plot.index = pd.to_datetime(sf_plot.index)
        if 'Volume' in sf_plot.columns:
            sf_plot['Volume'] = pd.to_numeric(sf_plot['Volume'], errors='coerce').fillna(0)

        self.ax.clear() 
        
        if self.var_candles.get():
            chart_type = 'candle'
        else:
            chart_type = 'line'

        try:
            mpf.plot(
                sf_plot, 
                type=chart_type,
                style='yahoo', 
                ax=self.ax, 
                volume=False, 
                show_nontrading=False,
                warn_too_much_data=1000000 
            )
            self.ax.set_title(f"{ticker} (Local DB)")
            self.ax.grid(True, linestyle='--', alpha=0.5)
            self.canvas.draw()
        except Exception as e:
            self.lbl_status.config(text="Plot Error.", foreground="red")
            messagebox.showerror("Plot Error", str(e))

    def _handle_error(
            self,
            msg
            ) -> None:

        self.lbl_status.config(text="Error.", foreground="red")
        messagebox.showerror("Database Error", msg)
