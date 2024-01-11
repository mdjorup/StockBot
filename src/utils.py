import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf


def get_historical_data(tickers, start_date, end_date):
    historical_data = {}
    print(tickers)
    for ticker in tickers:
        data = yf.download(ticker, start=start_date, end=end_date)
        if not data.empty:
            historical_data[ticker] = data
    return historical_data


def backtest_strategy(
    tickers,
    start_date: str,
    end_date: str,
    weekly_budget,
    rsi_period=14,
    oversold_threshold=95,
):
    historical_data = get_historical_data(tickers, start_date, end_date)

    portfolio = {}

    rsis = {}

    for ticker, data in historical_data.items():
        rsi = calculate_rsi(data["Close"], rsi_period)
        rsis[ticker] = rsi

    trading_start_date = (
        pd.to_datetime(start_date) + pd.Timedelta(days=rsi_period)
    ).strftime("%Y-%m-%d")
    trading_end_date = pd.to_datetime(end_date).strftime("%Y-%m-%d")
    weekly_trading_dates = pd.date_range(
        start=trading_start_date, end=trading_end_date, freq="W-FRI"
    )

    amount_invested = 0

    for date in weekly_trading_dates:
        oversold_stocks = []
        for ticker, rsi in rsis.items():
            if date not in rsi.index:
                continue
            ticker_rsi = rsi.loc[date]
            if ticker_rsi < oversold_threshold:
                oversold_stocks.append((ticker, ticker_rsi))

        allocation = allocate_budget(oversold_stocks, weekly_budget)

        for ticker, amount in allocation.items():
            stock_price = historical_data[ticker].loc[date, "Close"]
            num_shares = amount / stock_price
            amount_invested += amount
            portfolio[ticker] = portfolio.get(ticker, 0) + num_shares

    print("Portfolio: ", portfolio)

    # Calculate final portfolio value
    final_value = 0
    for ticker, shares in portfolio.items():
        final_stock_price = historical_data[ticker].iloc[-1]["Close"]
        final_value += shares * final_stock_price

    print("Amount invested: ", amount_invested)
    print("Final value: ", final_value)

    return


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
