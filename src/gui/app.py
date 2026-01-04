import tkinter as tk
from tkinter import ttk
import os
from src.gui.tabs.market_tab import MarketTab
from src.gui.tabs.download_tab import DownloadTab

class BabyBloombergApp(tk.Tk):

    def __init__(self):
        
        super().__init__()

        self.title("BabyBloomberg Terminal")
        self.geometry("1200x800") 
        self.minsize(800, 600)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        self._init_tabs()

    def _init_tabs(self) -> None:
        
        self.download_tab = DownloadTab(self.notebook)
        self.notebook.add(self.download_tab, text="Download Data")

        self.market_tab = MarketTab(self.notebook)
        self.notebook.add(self.market_tab, text="Visualize Market")

    def on_close(self) -> None:

        self.quit()
        self.destroy()
        os._exit(0)

    def run(self) -> None:
        self.mainloop()