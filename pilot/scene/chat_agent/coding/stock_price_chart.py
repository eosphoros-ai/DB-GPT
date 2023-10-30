# filename: stock_price_chart.py
import yfinance as yf
import matplotlib.pyplot as plt

# Define the ticker symbols for NVDA and TESLA
tickers = ["NVDA", "TSLA"]

# Fetch the historical stock price data for YTD
data = yf.download(tickers, start="2021-01-01", end="2021-12-31")

# Extract the 'Close' price column for each ticker
close_prices = data["Close"]

# Plot the stock price change YTD
close_prices.plot(title="Stock Price Change YTD", ylabel="Price (USD)")

# Display the chart
plt.show()
