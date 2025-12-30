from src.database import *
from src.strategy_manager import *

if __name__ == "__main__":
    
    ticker = "AAPL"

    sf = get_sf_from_sqlite(ticker)
    print(sf)
    
    start = get_primera_fecha(ticker)
    end = get_ultima_fecha(ticker)


    sell_at_dollar = SellStrat(ticker,start,end,100000000,sf,10,100)
    # sell_at_dollar.execute()
    # sell_at_dollar.print_performance()


    buy_at_dollar = BuyStrat(ticker,start,end,100000000,sf,8,100)
    # buy_at_dollar.execute()
    # buy_at_dollar.print_performance()

    new_strat = sell_at_dollar + buy_at_dollar
    new_strat.execute_sim()
    new_strat.print_performance()