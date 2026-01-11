"""Main entry point for the BabyBloomberg graphical user interface.

This module defines the primary application class `BabyBloombergApp`, which
initializes the main window, configures the layout, and manages the top-level
navigation tabs (Download, Visualization, and Strategy Creator).
"""

import tkinter as tk
from tkinter import ttk
import os
from src.gui.tabs.visualization_tab import VisualizationTab
from src.gui.tabs.download_tab import DownloadTab
from src.gui.tabs.strategy_creation_tab import StrategyCreationTab

class BabyBloombergApp(tk.Tk):
    """The main application window for the BabyBloomberg Terminal.

    Inherits from `tkinter.Tk` and serves as the root container for the application.
    It manages the lifecycle of the GUI, including window configuration, tab
    initialization, and the main event loop.

    Attributes:
        notebook (ttk.Notebook): The tabbed container widget holding the different
            functional modules (tabs) of the application.
        download_tab (DownloadTab): The instance of the data download tab.
        visualization_tab (VisualizationTab): The instance of the visualization tab.
        strategy_tab (StrategyCreationTab): The instance of the strategy creation tab.
    """

    notebook: ttk.Notebook
    download_tab: DownloadTab
    visualization_tab: VisualizationTab
    strategy_tab: StrategyCreationTab

    def __init__(self) -> None:
        """Initializes the main application window and its components.

        Sets the window title, dimensions, and close event protocol. It also
        instantiates the `ttk.Notebook` widget and calls `_init_tabs` to
        populate the interface.
        """

        super().__init__()

        self.title("BabyBloomberg Terminal")
        self.geometry("1200x800")
        self.minsize(800, 600)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)

        self._init_tabs()

    def _init_tabs(self) -> None:
        """Initializes and adds the functional tabs to the application notebook.

        Creates instances of `DownloadTab`, `VisualizationTab`, and `StrategyCreationTab`,
        and adds them to the `self.notebook` container with appropriate labels.
        """

        self.download_tab = DownloadTab(self.notebook)
        self.notebook.add(self.download_tab, text="Download Data")

        self.visualization_tab = VisualizationTab(self.notebook)
        self.notebook.add(self.visualization_tab, text="Visualization")

        self.strategy_tab = StrategyCreationTab(self.notebook)
        self.notebook.add(self.strategy_tab, text="Strategy Creator")

    def on_close(self) -> None:
        """Handles the window closure event.

        Ensures a clean exit by destroying the window widgets and forcing
        termination of the Python process to stop any background threads.
        """

        self.quit()
        self.destroy()
        os._exit(0)

    def run(self) -> None:
        """Starts the main event loop of the application.

        This method blocks execution until the window is closed by the user.
        """

        self.mainloop()