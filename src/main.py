from dataclasses import dataclass

import boto3
import yfinance as yf
from tabulate import tabulate

budget_per_oversold_stock = 90


tickers = [
    "AAPL",
    "AMZN",
    "MSFT",
    "TSLA",
    "CMG",
    "SPOT",
    "HOOD",
    "COST",
    "JPM",
    "CVS",
    "BTC-USD",
]  # Replace with your list of tickers


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


def get_stocks(tickers, period="1mo", rsi_period=14) -> list[Stock]:
    stocks: list[Stock] = []

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
    # Calculate the total of the inverse RSI values
    total_inverse_rsi = sum(stock.inverse_rsi for stock in oversold_stocks)

    # Allocate budget based on each stock's share of the total inverse RSI
    allocations = {}
    for stock in oversold_stocks:
        allocation = (stock.inverse_rsi / total_inverse_rsi) * budget
        allocations[stock] = allocation

    return allocations


def send_email_to_sns(subject, message):
    sns = boto3.client("sns", region_name="us-east-1")

    # Define the SNS topic ARN where you want to send the email
    topic_arn = "arn:aws:sns:us-east-1:057856323501:weekly-stocks"  # Replace 'YOUR_SNS_TOPIC_ARN' with your actual SNS topic ARN

    # Send the email to the SNS topic
    response = sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject=subject,
    )

    return response


def lambda_handler(event, context):
    stock_rsis = get_stocks(tickers)

    oversold_threshold = 30
    overbought_threshold = 70

    oversold_stocks: list[Stock] = []
    overbought_stocks: list[Stock] = []

    average_rsi = sum(stock.rsi for stock in stock_rsis) / len(stock_rsis)
    print(average_rsi)

    for stock in stock_rsis:
        if stock.rsi < oversold_threshold:
            oversold_stocks.append(stock)
        elif stock.rsi > overbought_threshold:
            overbought_stocks.append(stock)

    budget = budget_per_oversold_stock * len(oversold_stocks)

    allocation = allocate_budget(oversold_stocks, budget)

    total_allocation = sum(allocation.values())
    # [(ticker, amount), ...]

    oversold_stocks.sort(key=lambda x: x.rsi)
    overbought_stocks.sort(key=lambda x: x.rsi, reverse=True)

    overbought_stock_string = "\n".join(
        [
            f"{stock.ticker} - ${stock.price:.2f} - {stock.rsi:.2f} RSI"
            for stock in overbought_stocks
        ]
    )

    overbought_data = [
        [stock.ticker, f"${stock.price:.2f}", f"{stock.rsi:.2f} RSI"]
        for stock in overbought_stocks
    ]

    headers = ["Ticker", "Price", "RSI"]

    overbought_stock_string = tabulate(
        overbought_data, headers=headers, tablefmt="grid"
    )

    oversold_data = [
        [
            stock.ticker,
            f"${stock.price:.2f}",
            f"{stock.rsi:.2f} RSI",
            f"${amount:.2f}",
            f"{amount / budget * 100:.2f}%",
        ]
        for stock, amount in allocation.items()
    ]

    headers = ["Ticker", "Price", "RSI", "Amount to Allocate", "Budget %"]

    allocation_string = tabulate(oversold_data, headers=headers, tablefmt="grid")

    subject = "Weekly Stock Report"
    message = f"""
Here's your weekly stock report.

Overbought stocks: 
{overbought_stock_string}

Here's how you might allocate ${total_allocation:.2f} to the oversold stocks:
{allocation_string}
"""

    send_email_to_sns(subject, message)
