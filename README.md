# **BabyBloomberg — Automated Trading & Backtesting Engine**

This project implements a modular, object-oriented framework designed for the backtesting and simulation of automated trading strategies.  
The system is built to autonomously fetch historical S&P 500 market data via the Yahoo Finance API, managing data persistence through a local SQLite database to ensure efficient retrieval and processing during simulations.

The architecture supports the definition of custom trading logic (such as threshold-based Buy/Sell triggers) and features a multi-strategy manager (`MultiStrat`) capable of combining and executing various strategies simultaneously. The engine provides comprehensive performance metrics, including detailed operation logs, capital evolution tracking, and final return on investment (ROI) analysis.

## **Project Structure**

- **src/**: Contains the core logic of the application (API integration, database management, data processing, and strategy definitions).
- **data/**: Directory dedicated to storing the local SQLite database (`bolsa.db`).
- **main.py**: Entry point for executing simulations and backtesting workflows.

## **Installation & Usage**

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
## **Info and Socials**

**By:** Antonio Urbano Murillo  
**Email:** urbano@alu.comillas.edu  
**LinkedIn:** www.linkedin.com/in/a-urbano