class ErrorBaseDatos(Exception):
    """Se lanza cuando hay un problema específico con SQL o Access."""
    pass
class ErrorTickerYaActualizado(ErrorBaseDatos):
    """Se lanza cuando hay un problema específico con SQL o Access."""
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