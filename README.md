# BABYBLOOMBERG 📈

Un gestor de estrategias de trading automatizado escrito en Python. Este proyecto permite descargar datos históricos del S&P 500, almacenarlos en una base de datos SQLite y simular estrategias de compra/venta (Backtesting).

## Estructura del Proyecto

- **src/**: Contiene la lógica del programa (API, base de datos, procesamiento, estrategias).
- **data/**: Carpeta destinada a almacenar la base de datos `bolsa.db`.
- **main.py**: Punto de entrada para ejecutar las simulaciones.

## Instalación

1. Clona este repositorio.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt