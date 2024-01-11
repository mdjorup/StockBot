import boto3

from src.tickers import tickers
from src.utils import allocate_budget, get_stocks

budget = 250


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

    oversold_stocks = []  # [(ticker, rsi)]
    overbought_stocks = []  # [(ticker, rsi)]

    for stock in stock_rsis:
        if stock.rsi < oversold_threshold:
            oversold_stocks.append(stock)
        elif stock.rsi > overbought_threshold:
            overbought_stocks.append(stock)

    allocation = allocate_budget(oversold_stocks, budget)
    # [(ticker, amount), ...]

    oversold_stocks.sort(key=lambda x: x.rsi)
    overbought_stocks.sort(key=lambda x: x.rsi, reverse=True)

    overbought_stock_string = "\n".join(
        [
            f"{stock.ticker} - ${stock.price:.2f} - {stock.rsi:.2f} RSI"
            for stock in overbought_stocks
        ]
    )

    oversold_stock_string = "\n".join(
        [
            f"{stock.ticker} - ${stock.price:.2f} - {stock.rsi:.2f} RSI"
            for stock in oversold_stocks
        ]
    )

    allocation_string = "\n".join(
        [
            f"{stock.ticker} - ${amount:.2f} - {amount / budget * 100:.2f}%"
            for stock, amount in allocation.items()
        ]
    )

    subject = "Weekly Stock Report"
    message = f"""
Here's your weekly stock report.

Overbought stocks: 
{overbought_stock_string}

Oversold stocks: 
{oversold_stock_string}

Here's how you might allocate $250:
{allocation_string}
"""

    send_email_to_sns(subject, message)
