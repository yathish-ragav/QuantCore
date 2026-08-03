from quantcore.ingestion.yfinance import YahooFinanceClient

client = YahooFinanceClient()

symbol = "AAPL"

company = client.get_company_info(symbol)

print("=" * 70)
print("COMPANY")
print("=" * 70)

print(company)

print()

prices = client.get_price_history(symbol)

print("=" * 70)
print("LATEST PRICE")
print("=" * 70)

print(prices[-1])

print()

news = client.get_news(symbol)

print("=" * 70)
print("LATEST NEWS")
print("=" * 70)

for article in news[:3]:
    print()
    print(article)