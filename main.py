from src.database import *
from src.strategy_manager import *

if __name__ == "__main__":
    
    ticker = "AAPL"

    print(f"Cargando datos para {ticker}...")
    load_stock(ticker)

    sf = get_sf_from_sqlite(ticker)
    print(sf)
    
    start = get_primera_fecha(ticker)
    end = get_ultima_fecha(ticker)

    # hold = Strategy(ticker,start,end,100000000,sf)
    # hold.buy_all(start)
    # hold.close_trade(end)
    # hold.print_performance()

    sell_at_price = SellStrat(ticker,start,end,100000000,sf,10,100)
    # sell_at_price.execute()
    # sell_at_price.print_performance()

    buy_at_price = BuyStrat(ticker,start,end,100000000,sf,8,100)
    # buy_at_price.execute()
    # buy_at_price.print_performance()

    new_strat = sell_at_price + buy_at_price
    new_strat.execute_sim()
    new_strat.print_performance()
