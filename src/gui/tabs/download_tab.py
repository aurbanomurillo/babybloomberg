"""Data management interface for downloading financial data.

This module defines the `DownloadTab` class, which provides a GUI for users
to input ticker symbols and trigger the bulk download or update process
via the underlying database and API modules.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from src.database import load_stock

class DownloadTab(ttk.Frame):
    """A GUI tab for bulk downloading and updating stock market data.

    Provides a text input area for entering ticker symbols and a button to
    initiate the download process. Handles the execution in a separate thread
    to keep the UI responsive and displays progress via a progress bar.

    Attributes:
        txt_input (tk.Text): Text widget for user input of ticker symbols.
        btn_download (ttk.Button): Button to trigger the download process.
        lbl_status (ttk.Label): Label to display current status messages.
        progress (ttk.Progressbar): Visual indicator of the download progress.
    """

    def __init__(
            self,
            parent: tk.Widget
            ) -> None:
        """Initializes the download tab UI components.

        Args:
            parent (tk.Widget): The parent widget (typically a `ttk.Notebook`) to
                which this frame belongs.
        """

        super().__init__(parent)

        lbl_info: ttk.Label = ttk.Label(self, text="Enter Tickers to Download (separated by space or comma):", font=("Arial", 10, "bold"))
        lbl_info.pack(anchor="w", padx=20, pady=(20, 5))

        self.txt_input: tk.Text = tk.Text(self, height=5, width=60)
        self.txt_input.pack(padx=20, pady=5)
        self.txt_input.insert("1.0", "AAPL MSFT SPY")

        btn_frame: ttk.Frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=20, pady=10)

        self.btn_download: ttk.Button = ttk.Button(btn_frame, text="Download / Update All", command=self.on_download_click)
        self.btn_download.pack(side="left")

        self.lbl_status: ttk.Label = ttk.Label(self, text="Ready.", foreground="gray")
        self.lbl_status.pack(anchor="w", padx=20, pady=5)

        self.progress: ttk.Progressbar = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")

    def on_download_click(self) -> None:
        """Handles the click event for the 'Download / Update All' button.

        Retrieves the text from the input widget, parses it into a list of tickers,
        validates the input, and starts the `_bulk_download` method in a separate
        daemon thread.
        """

        raw_text = self.txt_input.get("1.0", tk.END)
        tickers = [t.strip().upper() for t in raw_text.replace(',', ' ').split() if t.strip()]

        if len(tickers) == 0:
            messagebox.showwarning("Input Error", "Please enter at least one ticker.")
            return

        self.btn_download.config(state="disabled")
        self.progress.pack(anchor="w", padx=20, pady=5)
        self.progress['value'] = 0
        self.progress['maximum'] = len(tickers)

        thread = threading.Thread(target=self._bulk_download, args=(tickers,), daemon=True)
        thread.start()

    def _bulk_download(
            self,
            tickers: list[str]
            ) -> None:
        """Executes the bulk download process for the specified tickers.

        Intended to run in a separate thread. Iterates through the list of tickers,
        calls `src.database.load_stock` for each, and updates the UI progress bar.
        Accumulates success and error counts.

        Args:
            tickers (list[str]): A list of ticker symbols to download.
        """

        success_count = 0
        errors = []

        for i, ticker in enumerate(tickers):

            self.after(0, lambda t=ticker: self.lbl_status.config(text=f"Downloading {t}... ({i+1}/{len(tickers)})", foreground="blue"))

            try:
                load_stock(ticker)
                success_count += 1
            except Exception as e:
                errors.append(f"{ticker}: {str(e)}")

            self.after(0, lambda v=i+1: self.progress.configure(value=v))

        self.after(0, self._finish_download, success_count, errors)

    def _finish_download(
            self,
            count: int,
            errors: list[str]
            ) -> None:
        """Updates the UI after the download thread completes.

        Re-enables the download button, hides the progress bar, and displays
        a summary message box with the results (success count and any errors).

        Args:
            count (int): The number of successfully updated tickers.
            errors (list[str]): A list of error messages encountered during the process.
        """

        self.btn_download.config(state="normal")
        self.progress.pack_forget()

        if not errors:
            self.lbl_status.config(text=f"Success! {count} tickers updated.", foreground="green")
            messagebox.showinfo("Complete", f"Successfully updated {count} tickers.")
        else:
            self.lbl_status.config(text=f"Finished with errors.", foreground="orange")
            err_msg = "\n".join(errors)
            messagebox.showwarning("Partial Success", f"Updated {count} tickers.\nErrors:\n{err_msg}")