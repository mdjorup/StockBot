from dataclasses import dataclass

import yfinance as yf


def calculate_rsi(data, window):
    delta = data.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0

    gain = up.rolling(window=window, min_periods=1).mean()
    loss = down.abs().rolling(window=window, min_periods=1).mean()

    RS = gain / loss
    RSI = 100 - (100 / (1 + RS))

    return RSI


@dataclass
class Stock:
    ticker: str
    rsi: float
    inverse_rsi: float
    price: float
    url: str

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return self.ticker == other.ticker


def get_stocks(tickers, period="1mo", rsi_period=14):
    stocks = []

    for ticker in tickers:
        data = yf.download(ticker, period=period)
        if not data.empty:
            data["RSI"] = calculate_rsi(data["Close"], rsi_period)
            last_rsi = data["RSI"].iloc[-1]

            new_stock = Stock(
                ticker,
                last_rsi,
                1 / last_rsi,
                data["Close"].iloc[-1],
                f"https://finance.yahoo.com/quote/{ticker}",
            )
            stocks.append(new_stock)
        # https://finance.yahoo.com/quote/AAPL

    return stocks


def allocate_budget(oversold_stocks, budget):
    # Calculate the inverse of the RSI for each stock

    # Calculate the total of the inverse RSI values
    total_inverse_rsi = sum(stock.inverse_rsi for stock in oversold_stocks)

    # Allocate budget based on each stock's share of the total inverse RSI
    allocations = {}
    for stock in oversold_stocks:
        allocation = (stock.inverse_rsi / total_inverse_rsi) * budget
        allocations[stock] = allocation

    return allocations
