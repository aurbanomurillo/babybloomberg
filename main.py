"""Entry point for the BabyBloomberg application.

This script initializes the main application window and starts the event loop.
"""

from src.gui.app import BabyBloombergApp

if __name__ == "__main__":
    app = BabyBloombergApp()
    app.run()