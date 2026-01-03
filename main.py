from src.database import *
from src.strategy import *
from src.multi_strategy import *
from src.buy import *
from src.sell import *
from src.bounded import *
from src.multi_bounded import *

if __name__ == "__main__":
    
    ticker = "AAPL"

    # print(f"Cargando datos para {ticker}...")
    # load_stock(ticker)


    sf = get_sf_from_sqlite(ticker)
    print(sf)
    
    start = get_primera_fecha(sf)
    end = get_ultima_fecha(sf)

    capital = 1000000
    input()

    hold = Strategy(ticker, start, end, capital, sf)
    hold.buy_all(start)
    hold.close_trade(end)
    hold.print_operations()
    hold.print_performance()
    input()

    sell_at_price = SellStrategy(ticker,start,end,capital,sf,0.01,(0.12,0.14),sizing_type="percentage current")
    sell_at_price.execute()
    sell_at_price.print_operations()
    sell_at_price.print_performance()
    input()

    buy_at_price = BuyStrategy(ticker,start,end,capital,sf,0.01,(0.08,0.10), sizing_type="percentage initial")
    buy_at_price.execute()
    buy_at_price.print_operations()
    buy_at_price.print_performance()
    input()

    sell_at_price = SellStrategy(ticker,start,end,capital,sf,0.01,(0.12,0.14),sizing_type="percentage current")
    buy_at_price = BuyStrategy(ticker,start,end,capital,sf,0.01,(0.08,0.10), sizing_type="percentage initial")
    new_strat = sell_at_price + buy_at_price
    new_strat.print_operations()
    new_strat.execute()
    new_strat.print_performance()
    input()

    sell_scare = DynamicSellStrategy(ticker,start,end,capital,sf,1,-0.03,"1 day")
    sell_scare.execute()
    sell_scare.print_operations()
    sell_scare.print_performance()
    input()

    buy_dip = DynamicBuyStrategy(ticker,start,end,capital,sf,1,-0.03,"1 day")
    buy_dip.execute()
    buy_dip.print_operations()
    buy_dip.print_performance()
    input()

    late_start = "2024-01-02"
    sltp = BoundedStrategy(ticker, late_start, end, capital, sf, 150, 500) 
    sltp.execute()
    sltp.print_operations()
    sltp.print_performance()
    input()

    specific_sltp = MultiBoundedStrategy(ticker, start, end, capital, sf, [0.08, 0.1], 1, -0.9, 2)
    specific_sltp.execute()
    specific_sltp.print_operations()
    specific_sltp.print_performance()
    input()

    sltp_dip = MultiDynamicBoundedStrategy(ticker, start, end, capital, sf, 0.01, -0.02, +0.02, -0.04, "3 days", max_holding_period="3 d", sizing_type="percentage current")
    sltp_dip.execute()
    sltp_dip.print_operations()
    sltp_dip.print_performance()
    input()
