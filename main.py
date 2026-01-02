from src.database import *
from src.strategy_manager import *
from src.multi_strategy_manager import *
from src.buy_strategy import *
from src.sell_strategy import *

if __name__ == "__main__":
    
    ticker = "AAPL"

    # print(f"Cargando datos para {ticker}...")
    # load_stock(ticker)


    sf = get_sf_from_sqlite(ticker)
    print(sf)
    
    start = get_primera_fecha(sf)
    end = get_ultima_fecha(sf)


    # hold = Strategy(ticker, start, end, 100000000, sf)
    # hold.buy_all(start)
    # hold.close_trade(end)
    # hold.print_performance()


    # sell_at_price = SellStrat(ticker,start,end,1000000,sf,1,(0.12,0.14))
    # sell_at_price.execute()
    # sell_at_price.print_performance()

    # buy_at_price = BuyStrat(ticker,start,end,1000000,sf,1,(0.08,0.10))
    # buy_at_price.execute()
    # buy_at_price.print_performance()

    # sell_at_price = SellStrat(ticker,start,end,1000000,sf,1,(0.12,0.14))
    # buy_at_price = BuyStrat(ticker,start,end,1000000,sf,1,(0.08,0.10))
    # new_strat = sell_at_price + buy_at_price
    # new_strat.execute_sim()
    # new_strat.print_performance()

    # sell_scare = DynamicSellStrat(ticker,start,end,1000000,sf,1,-0.03,"1 day")
    # sell_scare.execute()
    # sell_scare.print_operations()
    # sell_scare.print_performance()

    buy_dip = DynamicBuyStrat(ticker,start,end,1000000,sf,1,-0.03,"1 day")
    buy_dip.execute()
    buy_dip.print_operations()
    buy_dip.print_performance()
