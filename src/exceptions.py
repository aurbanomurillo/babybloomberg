class ErrorBaseDatos(Exception):
    pass
class ErrorTickerYaActualizado(ErrorBaseDatos):
    pass
class NotEnoughError(Exception):
    pass
class NotEnoughCashError(NotEnoughError):
    pass
class NotEnoughStockError(NotEnoughError):
    pass
class TradeNotClosed(Exception):
    pass
class StopChecking(Exception):
    pass
