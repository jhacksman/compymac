# Financial Information Research (#4)

## Overview

This document provides comprehensive research on implementing financial information capabilities for the PASSFEL (Personal ASSistant For Everyday Life) project. The research covers stock market data, cryptocurrency prices, currency exchange rates, and related financial APIs to enable real-time financial information retrieval and monitoring.

## Research Methodology

Solutions are categorized by complexity to prioritize implementation:
- **Simple**: Ready-to-use APIs or libraries, minimal setup, good documentation, free or low cost
- **Moderate**: Requires API keys or configuration, moderate complexity, well-documented, reasonable pricing
- **Complex**: Complex setup, limited documentation, significant implementation overhead, or expensive

## Stock Market Data Sources

### 1. yfinance (Yahoo Finance) ⭐ RECOMMENDED (Simple)

**Overview:**
yfinance is an unofficial Python library that provides a Pythonic way to download financial and market data from Yahoo Finance. It's widely used and actively maintained.

**Key Features:**
- Real-time and historical stock data
- Company fundamentals and financials
- Options data
- Dividend and split information
- Market indices
- No API key required
- Free to use

**Important Note:**
yfinance is an unofficial library that scrapes Yahoo Finance. While widely used, it's not officially supported by Yahoo and may break if Yahoo changes their website structure. However, it's actively maintained and has a large community.

**Installation:**
```bash
pip install yfinance
```

**Python Integration:**
```python
import yfinance as yf
from datetime import datetime, timedelta

class StockDataClient:
    def __init__(self):
        pass
    
    def get_current_price(self, symbol):
        """Get current stock price"""
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            return {
                "symbol": symbol,
                "price": data['Close'].iloc[-1],
                "volume": data['Volume'].iloc[-1],
                "timestamp": data.index[-1].isoformat()
            }
        return None
    
    def get_quote(self, symbol):
        """Get detailed quote information"""
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            "symbol": symbol,
            "name": info.get("longName", ""),
            "price": info.get("currentPrice", info.get("regularMarketPrice")),
            "change": info.get("regularMarketChange"),
            "change_percent": info.get("regularMarketChangePercent"),
            "open": info.get("regularMarketOpen"),
            "high": info.get("dayHigh"),
            "low": info.get("dayLow"),
            "volume": info.get("volume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow")
        }
    
    def get_historical_data(self, symbol, period="1mo", interval="1d"):
        """Get historical price data
        
        Valid periods: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        """
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)
        
        return {
            "symbol": symbol,
            "data": [
                {
                    "date": index.isoformat(),
                    "open": row['Open'],
                    "high": row['High'],
                    "low": row['Low'],
                    "close": row['Close'],
                    "volume": row['Volume']
                }
                for index, row in data.iterrows()
            ]
        }
    
    def get_company_info(self, symbol):
        """Get company information and fundamentals"""
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            "symbol": symbol,
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "market_cap": info.get("marketCap"),
            "revenue": info.get("totalRevenue"),
            "profit_margin": info.get("profitMargins"),
            "dividend_yield": info.get("dividendYield")
        }
    
    def get_multiple_quotes(self, symbols):
        """Get quotes for multiple symbols efficiently"""
        tickers = yf.Tickers(" ".join(symbols))
        results = []
        
        for symbol in symbols:
            try:
                ticker = tickers.tickers[symbol]
                info = ticker.info
                results.append({
                    "symbol": symbol,
                    "price": info.get("currentPrice", info.get("regularMarketPrice")),
                    "change_percent": info.get("regularMarketChangePercent"),
                    "name": info.get("longName", symbol)
                })
            except Exception as e:
                results.append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return results

# Usage Examples
stock_client = StockDataClient()

# Get current price
price_data = stock_client.get_current_price("AAPL")
print(f"AAPL: ${price_data['price']:.2f}")

# Get detailed quote
quote = stock_client.get_quote("TSLA")
print(f"{quote['name']}: ${quote['price']:.2f} ({quote['change_percent']:.2f}%)")

# Get historical data
historical = stock_client.get_historical_data("MSFT", period="1mo", interval="1d")
print(f"Retrieved {len(historical['data'])} days of data")

# Get company info
company = stock_client.get_company_info("GOOGL")
print(f"{company['name']} - {company['sector']}")

# Get multiple quotes
quotes = stock_client.get_multiple_quotes(["AAPL", "MSFT", "GOOGL", "AMZN"])
for q in quotes:
    if "error" not in q:
        print(f"{q['symbol']}: ${q['price']:.2f}")
```

**Supported Symbols:**
- US stocks: AAPL, MSFT, GOOGL, TSLA, etc.
- Indices: ^GSPC (S&P 500), ^DJI (Dow Jones), ^IXIC (NASDAQ)
- ETFs: SPY, QQQ, VOO, etc.
- International stocks: Use Yahoo Finance symbol format (e.g., 0700.HK for Tencent)

**Rate Limits:**
- No official rate limits documented
- Recommended: Limit to 2000 requests/hour to avoid being blocked
- Use caching for frequently accessed data

**Implementation Complexity:** Simple
- No API key required
- Easy to use Python library
- Comprehensive data coverage
- Active community support

**Limitations:**
- Unofficial library (may break if Yahoo changes their site)
- No guaranteed SLA or support
- Real-time data may have 15-minute delay for some markets
- Intraday data limited to last 60 days

**Use Cases for PASSFEL:**
- Real-time stock price monitoring
- Portfolio tracking
- Market indices tracking
- Company research and fundamentals

---

### 2. Alpha Vantage API (Moderate)

**Overview:**
Alpha Vantage provides enterprise-grade financial market data through a free API with generous rate limits.

**Key Features:**
- Real-time and historical stock data
- Technical indicators
- Forex and cryptocurrency data
- Fundamental data
- Economic indicators
- Free tier available

**API Details:**
- **Base URL**: `https://www.alphavantage.co/query`
- **Authentication**: API key required (free)
- **Rate Limits**: 25 requests/day (free tier), 500 requests/day (premium $49.99/month)
- **Format**: JSON, CSV

**Getting API Key:**
1. Visit https://www.alphavantage.co/support/#api-key
2. Fill out form (free, no credit card required)
3. Receive API key instantly

**Python Integration:**
```python
import requests

class AlphaVantageClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
    
    def get_quote(self, symbol):
        """Get real-time quote"""
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        data = response.json()
        
        if "Global Quote" in data:
            quote = data["Global Quote"]
            return {
                "symbol": quote.get("01. symbol"),
                "price": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%").rstrip("%"),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day")
            }
        return None
    
    def get_intraday_data(self, symbol, interval="5min"):
        """Get intraday time series data
        
        Valid intervals: 1min, 5min, 15min, 30min, 60min
        """
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": symbol,
            "interval": interval,
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        return response.json()
    
    def get_daily_data(self, symbol, outputsize="compact"):
        """Get daily time series data
        
        outputsize: compact (100 data points) or full (20+ years)
        """
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": outputsize,
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        return response.json()
    
    def get_company_overview(self, symbol):
        """Get company fundamental data"""
        params = {
            "function": "OVERVIEW",
            "symbol": symbol,
            "apikey": self.api_key
        }
        response = requests.get(self.base_url, params=params)
        return response.json()

# Usage
av_client = AlphaVantageClient("YOUR_API_KEY")
quote = av_client.get_quote("IBM")
print(f"IBM: ${quote['price']:.2f} ({quote['change_percent']}%)")
```

**Implementation Complexity:** Moderate
- Requires API key (free but limited)
- Well-documented API
- Rate limits are restrictive on free tier
- Good for occasional queries

**Pricing:**
- **Free**: 25 requests/day
- **Premium**: $49.99/month for 500 requests/day
- **Enterprise**: Custom pricing for higher limits

**Use Cases for PASSFEL:**
- Backup data source for yfinance
- Technical indicators
- Economic data
- Fundamental analysis

---

### 3. Finnhub API (Moderate)

**Overview:**
Finnhub provides real-time stock market data, financial news, and alternative data through a RESTful API.

**Key Features:**
- Real-time stock quotes
- Financial news
- Company profiles
- Earnings calendar
- IPO calendar
- Free tier available

**API Details:**
- **Base URL**: `https://finnhub.io/api/v1`
- **Authentication**: API key required (free tier available)
- **Rate Limits**: 60 calls/minute (free tier)
- **Format**: JSON

**Pricing:**
- **Free**: 60 API calls/minute
- **Starter**: $19.99/month for 300 calls/minute
- **Professional**: $59.99/month for 600 calls/minute

**Implementation Complexity:** Moderate
- Requires API key
- Good documentation
- Reasonable free tier
- Real-time data available

---

## Cryptocurrency Data Sources

### 4. CoinGecko API ⭐ RECOMMENDED (Simple to Moderate)

**Overview:**
CoinGecko provides comprehensive cryptocurrency data including prices, market data, trading volume, and historical data for 10,000+ cryptocurrencies.

**Key Features:**
- 10,000+ cryptocurrencies
- Real-time prices and market data
- Historical data
- Exchange data
- DeFi data
- NFT data
- Free tier available (Demo plan)

**API Details:**
- **Base URL**: `https://api.coingecko.com/api/v3`
- **Authentication**: API key required (free Demo plan available)
- **Rate Limits**: 10-30 calls/minute (Demo plan)
- **Format**: JSON

**Pricing:**
- **Demo**: Free (10-30 calls/minute, no credit card required)
- **Analyst**: $129/month (500 calls/minute)
- **Lite**: $499/month (1000 calls/minute)
- **Pro**: $999/month (2000 calls/minute)

**Python Integration:**
```python
import requests
from datetime import datetime

class CoinGeckoClient:
    def __init__(self, api_key=None):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {}
        if api_key:
            self.headers["x-cg-demo-api-key"] = api_key
    
    def get_price(self, coin_ids, vs_currencies="usd"):
        """Get current price for cryptocurrencies
        
        coin_ids: comma-separated string or list (e.g., "bitcoin,ethereum")
        vs_currencies: comma-separated string (e.g., "usd,eur")
        """
        if isinstance(coin_ids, list):
            coin_ids = ",".join(coin_ids)
        
        params = {
            "ids": coin_ids,
            "vs_currencies": vs_currencies,
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true"
        }
        
        response = requests.get(
            f"{self.base_url}/simple/price",
            params=params,
            headers=self.headers
        )
        return response.json()
    
    def get_coin_data(self, coin_id):
        """Get detailed data for a specific cryptocurrency"""
        response = requests.get(
            f"{self.base_url}/coins/{coin_id}",
            params={"localization": "false", "tickers": "false"},
            headers=self.headers
        )
        data = response.json()
        
        return {
            "id": data.get("id"),
            "symbol": data.get("symbol"),
            "name": data.get("name"),
            "price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
            "market_cap": data.get("market_data", {}).get("market_cap", {}).get("usd"),
            "total_volume": data.get("market_data", {}).get("total_volume", {}).get("usd"),
            "price_change_24h": data.get("market_data", {}).get("price_change_percentage_24h"),
            "market_cap_rank": data.get("market_cap_rank"),
            "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
            "total_supply": data.get("market_data", {}).get("total_supply"),
            "ath": data.get("market_data", {}).get("ath", {}).get("usd"),
            "atl": data.get("market_data", {}).get("atl", {}).get("usd")
        }
    
    def get_market_chart(self, coin_id, vs_currency="usd", days=7):
        """Get historical market data
        
        days: 1, 7, 14, 30, 90, 180, 365, max
        """
        params = {
            "vs_currency": vs_currency,
            "days": days
        }
        
        response = requests.get(
            f"{self.base_url}/coins/{coin_id}/market_chart",
            params=params,
            headers=self.headers
        )
        data = response.json()
        
        # Convert timestamps to readable format
        prices = [
            {
                "timestamp": datetime.fromtimestamp(p[0] / 1000).isoformat(),
                "price": p[1]
            }
            for p in data.get("prices", [])
        ]
        
        return {
            "coin_id": coin_id,
            "vs_currency": vs_currency,
            "prices": prices
        }
    
    def get_trending_coins(self):
        """Get trending cryptocurrencies"""
        response = requests.get(
            f"{self.base_url}/search/trending",
            headers=self.headers
        )
        data = response.json()
        
        return [
            {
                "id": coin["item"]["id"],
                "name": coin["item"]["name"],
                "symbol": coin["item"]["symbol"],
                "market_cap_rank": coin["item"]["market_cap_rank"],
                "price_btc": coin["item"]["price_btc"]
            }
            for coin in data.get("coins", [])
        ]
    
    def search_coins(self, query):
        """Search for cryptocurrencies"""
        params = {"query": query}
        response = requests.get(
            f"{self.base_url}/search",
            params=params,
            headers=self.headers
        )
        data = response.json()
        
        return [
            {
                "id": coin["id"],
                "name": coin["name"],
                "symbol": coin["symbol"],
                "market_cap_rank": coin.get("market_cap_rank")
            }
            for coin in data.get("coins", [])[:10]  # Limit to top 10 results
        ]

# Usage Examples
coingecko = CoinGeckoClient(api_key="YOUR_API_KEY")  # or None for public API

# Get current prices
prices = coingecko.get_price(["bitcoin", "ethereum", "cardano"])
print(f"Bitcoin: ${prices['bitcoin']['usd']:,.2f}")
print(f"Ethereum: ${prices['ethereum']['usd']:,.2f}")

# Get detailed coin data
btc_data = coingecko.get_coin_data("bitcoin")
print(f"{btc_data['name']} ({btc_data['symbol'].upper()})")
print(f"Price: ${btc_data['price_usd']:,.2f}")
print(f"24h Change: {btc_data['price_change_24h']:.2f}%")
print(f"Market Cap Rank: #{btc_data['market_cap_rank']}")

# Get historical data
chart_data = coingecko.get_market_chart("ethereum", days=7)
print(f"Retrieved {len(chart_data['prices'])} price points")

# Get trending coins
trending = coingecko.get_trending_coins()
print("Trending cryptocurrencies:")
for coin in trending[:5]:
    print(f"  {coin['name']} ({coin['symbol']})")

# Search for coins
results = coingecko.search_coins("polkadot")
for coin in results:
    print(f"{coin['name']} ({coin['symbol']}) - Rank #{coin['market_cap_rank']}")
```

**Common Coin IDs:**
- Bitcoin: `bitcoin`
- Ethereum: `ethereum`
- Cardano: `cardano`
- Solana: `solana`
- Polkadot: `polkadot`
- Dogecoin: `dogecoin`
- Ripple: `ripple`

**Implementation Complexity:** Simple to Moderate
- Free Demo plan available (no credit card)
- Well-documented API
- Comprehensive cryptocurrency coverage
- Rate limits are reasonable for personal use

**Use Cases for PASSFEL:**
- Cryptocurrency price monitoring
- Portfolio tracking
- Market trends
- Price alerts

---

## Currency Exchange Rate Sources

### 5. Frankfurter API ⭐ RECOMMENDED (Simple)

**Overview:**
Frankfurter is a free, open-source API for current and historical foreign exchange rates published by the European Central Bank.

**Key Features:**
- 33 currencies
- Daily updates
- Historical data since 1999
- No API key required
- No rate limits
- Free and open source

**API Details:**
- **Base URL**: `https://api.frankfurter.app`
- **Authentication**: None required
- **Rate Limits**: None
- **Format**: JSON
- **Data Source**: European Central Bank

**Python Integration:**
```python
import requests
from datetime import datetime, timedelta

class CurrencyExchangeClient:
    def __init__(self):
        self.base_url = "https://api.frankfurter.app"
    
    def get_latest_rates(self, base="USD", symbols=None):
        """Get latest exchange rates
        
        base: Base currency (default: USD)
        symbols: Comma-separated list of target currencies (optional)
        """
        params = {"from": base}
        if symbols:
            params["to"] = symbols
        
        response = requests.get(f"{self.base_url}/latest", params=params)
        data = response.json()
        
        return {
            "base": data["base"],
            "date": data["date"],
            "rates": data["rates"]
        }
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Convert amount from one currency to another"""
        params = {
            "from": from_currency,
            "to": to_currency,
            "amount": amount
        }
        
        response = requests.get(f"{self.base_url}/latest", params=params)
        data = response.json()
        
        return {
            "amount": amount,
            "from": from_currency,
            "to": to_currency,
            "rate": data["rates"][to_currency],
            "converted_amount": data["rates"][to_currency] * amount,
            "date": data["date"]
        }
    
    def get_historical_rates(self, date, base="USD"):
        """Get exchange rates for a specific date
        
        date: YYYY-MM-DD format
        """
        response = requests.get(f"{self.base_url}/{date}", params={"from": base})
        return response.json()
    
    def get_time_series(self, start_date, end_date, base="USD", symbols=None):
        """Get exchange rates for a date range
        
        start_date: YYYY-MM-DD format
        end_date: YYYY-MM-DD format
        """
        params = {"from": base}
        if symbols:
            params["to"] = symbols
        
        url = f"{self.base_url}/{start_date}..{end_date}"
        response = requests.get(url, params=params)
        return response.json()
    
    def get_available_currencies(self):
        """Get list of available currencies"""
        response = requests.get(f"{self.base_url}/currencies")
        return response.json()

# Usage Examples
fx_client = CurrencyExchangeClient()

# Get latest rates
rates = fx_client.get_latest_rates(base="USD", symbols="EUR,GBP,JPY")
print(f"1 USD = {rates['rates']['EUR']:.4f} EUR")
print(f"1 USD = {rates['rates']['GBP']:.4f} GBP")
print(f"1 USD = {rates['rates']['JPY']:.2f} JPY")

# Convert currency
conversion = fx_client.convert_currency(100, "USD", "EUR")
print(f"{conversion['amount']} {conversion['from']} = {conversion['converted_amount']:.2f} {conversion['to']}")
print(f"Exchange rate: {conversion['rate']:.4f}")

# Get historical rates
historical = fx_client.get_historical_rates("2024-01-01", base="USD")
print(f"Rates on {historical['date']}:")
for currency, rate in list(historical['rates'].items())[:5]:
    print(f"  1 USD = {rate:.4f} {currency}")

# Get time series
time_series = fx_client.get_time_series("2024-01-01", "2024-01-31", base="USD", symbols="EUR")
print(f"EUR rates for January 2024: {len(time_series['rates'])} data points")

# Get available currencies
currencies = fx_client.get_available_currencies()
print(f"Available currencies: {len(currencies)}")
for code, name in list(currencies.items())[:10]:
    print(f"  {code}: {name}")
```

**Supported Currencies:**
- Major: USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD
- Asian: CNY, HKD, SGD, KRW, INR, THB
- European: SEK, NOK, DKK, PLN, CZK, HUF
- Others: BRL, MXN, ZAR, TRY, RUB
- Total: 33 currencies

**Implementation Complexity:** Simple
- No API key required
- No rate limits
- Simple REST API
- Reliable data from ECB

**Limitations:**
- Limited to 33 currencies
- Daily updates only (no intraday data)
- No cryptocurrency support

**Use Cases for PASSFEL:**
- Currency conversion
- Exchange rate monitoring
- Travel planning
- International transactions

---

### 6. ExchangeRate-API (Simple)

**Overview:**
ExchangeRate-API provides simple and reliable currency conversion data with a free tier.

**Key Features:**
- 161 currencies
- Real-time rates
- Historical data
- Free tier: 1,500 requests/month
- No credit card required

**API Details:**
- **Base URL**: `https://v6.exchangerate-api.com/v6/{API_KEY}`
- **Authentication**: API key required (free)
- **Rate Limits**: 1,500 requests/month (free tier)
- **Format**: JSON

**Pricing:**
- **Free**: 1,500 requests/month
- **Basic**: $9.99/month for 100,000 requests
- **Professional**: $24.99/month for 500,000 requests

**Implementation Complexity:** Simple
- Requires free API key
- Simple to use
- More currencies than Frankfurter
- Reasonable free tier

---

## Integrated Financial Data System

**Complete Financial Data Client:**
```python
import time
from datetime import datetime

class FinancialDataSystem:
    def __init__(self, coingecko_key=None, alphavantage_key=None):
        self.stock_client = StockDataClient()
        self.crypto_client = CoinGeckoClient(coingecko_key)
        self.fx_client = CurrencyExchangeClient()
        self.cache = {}
        self.cache_ttl = 60  # seconds
    
    def get_stock_quote(self, symbol):
        """Get stock quote with caching"""
        cache_key = f"stock:{symbol}"
        
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            quote = self.stock_client.get_quote(symbol)
            self._cache_data(cache_key, quote)
            return quote
        except Exception as e:
            return {"error": str(e), "symbol": symbol}
    
    def get_crypto_price(self, coin_id):
        """Get cryptocurrency price with caching"""
        cache_key = f"crypto:{coin_id}"
        
        if self._is_cached(cache_key):
            return self.cache[cache_key]["data"]
        
        try:
            data = self.crypto_client.get_coin_data(coin_id)
            self._cache_data(cache_key, data)
            return data
        except Exception as e:
            return {"error": str(e), "coin_id": coin_id}
    
    def convert_currency(self, amount, from_currency, to_currency):
        """Convert currency with caching"""
        cache_key = f"fx:{from_currency}:{to_currency}"
        
        if self._is_cached(cache_key):
            rate = self.cache[cache_key]["data"]["rate"]
            return {
                "amount": amount,
                "from": from_currency,
                "to": to_currency,
                "rate": rate,
                "converted_amount": amount * rate,
                "cached": True
            }
        
        try:
            conversion = self.fx_client.convert_currency(amount, from_currency, to_currency)
            self._cache_data(cache_key, conversion)
            return conversion
        except Exception as e:
            return {"error": str(e)}
    
    def get_portfolio_value(self, portfolio):
        """Calculate total portfolio value
        
        portfolio: dict with format:
        {
            "stocks": {"AAPL": 10, "MSFT": 5},
            "crypto": {"bitcoin": 0.5, "ethereum": 2},
            "cash": {"USD": 1000, "EUR": 500}
        }
        """
        total_usd = 0
        details = []
        
        # Calculate stock values
        for symbol, quantity in portfolio.get("stocks", {}).items():
            quote = self.get_stock_quote(symbol)
            if "error" not in quote:
                value = quote["price"] * quantity
                total_usd += value
                details.append({
                    "type": "stock",
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": quote["price"],
                    "value_usd": value
                })
        
        # Calculate crypto values
        for coin_id, quantity in portfolio.get("crypto", {}).items():
            crypto_data = self.get_crypto_price(coin_id)
            if "error" not in crypto_data:
                value = crypto_data["price_usd"] * quantity
                total_usd += value
                details.append({
                    "type": "crypto",
                    "symbol": crypto_data["symbol"],
                    "quantity": quantity,
                    "price": crypto_data["price_usd"],
                    "value_usd": value
                })
        
        # Calculate cash values
        for currency, amount in portfolio.get("cash", {}).items():
            if currency == "USD":
                total_usd += amount
                details.append({
                    "type": "cash",
                    "currency": currency,
                    "amount": amount,
                    "value_usd": amount
                })
            else:
                conversion = self.convert_currency(amount, currency, "USD")
                if "error" not in conversion:
                    total_usd += conversion["converted_amount"]
                    details.append({
                        "type": "cash",
                        "currency": currency,
                        "amount": amount,
                        "value_usd": conversion["converted_amount"]
                    })
        
        return {
            "total_value_usd": total_usd,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
    
    def _is_cached(self, key):
        """Check if data is cached and not expired"""
        if key in self.cache:
            age = time.time() - self.cache[key]["timestamp"]
            return age < self.cache_ttl
        return False
    
    def _cache_data(self, key, data):
        """Cache data with timestamp"""
        self.cache[key] = {
            "data": data,
            "timestamp": time.time()
        }

# Usage Example
financial_system = FinancialDataSystem()

# Get stock quote
aapl = financial_system.get_stock_quote("AAPL")
print(f"Apple: ${aapl['price']:.2f}")

# Get crypto price
btc = financial_system.get_crypto_price("bitcoin")
print(f"Bitcoin: ${btc['price_usd']:,.2f}")

# Convert currency
conversion = financial_system.convert_currency(100, "USD", "EUR")
print(f"$100 USD = €{conversion['converted_amount']:.2f} EUR")

# Calculate portfolio value
portfolio = {
    "stocks": {"AAPL": 10, "MSFT": 5},
    "crypto": {"bitcoin": 0.1, "ethereum": 1},
    "cash": {"USD": 5000, "EUR": 1000}
}

portfolio_value = financial_system.get_portfolio_value(portfolio)
print(f"\nPortfolio Total Value: ${portfolio_value['total_value_usd']:,.2f}")
print("\nBreakdown:")
for item in portfolio_value['details']:
    print(f"  {item['type'].upper()}: {item.get('symbol', item.get('currency'))} - ${item['value_usd']:,.2f}")
```

---

## Implementation Recommendations

### Phase 1: Core Financial Data (Immediate Implementation)

1. **yfinance for Stocks**
   - Implement StockDataClient for stock market data
   - Add caching to reduce API calls
   - Set up quote retrieval and historical data
   - **Rationale**: Free, comprehensive, no API key required

2. **Frankfurter for Currency Exchange**
   - Implement CurrencyExchangeClient for FX rates
   - Add currency conversion functionality
   - Set up rate monitoring
   - **Rationale**: Free, reliable, no API key, ECB data

3. **CoinGecko for Cryptocurrency**
   - Sign up for free Demo API key
   - Implement CoinGeckoClient for crypto prices
   - Add top cryptocurrencies monitoring
   - **Rationale**: Free tier available, comprehensive coverage

### Phase 2: Enhanced Features (Short-term)

4. **Portfolio Tracking**
   - Implement portfolio value calculation
   - Add multi-asset support (stocks, crypto, cash)
   - Create portfolio performance tracking
   - **Rationale**: High value feature for users

5. **Price Alerts**
   - Implement price monitoring system
   - Add threshold-based alerts
   - Create notification system
   - **Rationale**: Proactive user engagement

### Phase 3: Advanced Data (Medium-term, Optional)

6. **Alpha Vantage Integration (Optional)**
   - Sign up for free API key
   - Implement as backup for yfinance
   - Add technical indicators
   - **Rationale**: Provides official API with SLA

7. **Historical Analysis**
   - Implement historical data retrieval
   - Add charting capabilities
   - Create trend analysis
   - **Rationale**: Enhanced user insights

---

## Caching and Performance

**Cache Implementation:**
```python
import json
import hashlib
from datetime import datetime, timedelta

class FinancialDataCache:
    def __init__(self, db_connection):
        self.conn = db_connection
        self._create_table()
    
    def _create_table(self):
        """Create cache table"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS financial_cache (
                    cache_key TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS financial_cache_expires_idx 
                ON financial_cache(expires_at);
                
                CREATE INDEX IF NOT EXISTS financial_cache_symbol_idx 
                ON financial_cache(symbol, data_type);
            """)
            self.conn.commit()
    
    def get(self, data_type, symbol):
        """Get cached financial data"""
        cache_key = self._generate_key(data_type, symbol)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT data FROM financial_cache
                WHERE cache_key = %s AND expires_at > NOW()
            """, (cache_key,))
            
            result = cur.fetchone()
            return result[0] if result else None
    
    def set(self, data_type, symbol, data, ttl_minutes=5):
        """Cache financial data"""
        cache_key = self._generate_key(data_type, symbol)
        expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO financial_cache (cache_key, data_type, symbol, data, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (cache_key) DO UPDATE
                SET data = EXCLUDED.data,
                    created_at = CURRENT_TIMESTAMP,
                    expires_at = EXCLUDED.expires_at
            """, (cache_key, data_type, symbol, json.dumps(data), expires_at))
            self.conn.commit()
    
    def _generate_key(self, data_type, symbol):
        """Generate cache key"""
        combined = f"{data_type}:{symbol.upper()}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM financial_cache WHERE expires_at < NOW()")
            deleted = cur.rowcount
            self.conn.commit()
            return deleted
```

**Cache TTL Recommendations:**
- Stock quotes: 1-5 minutes
- Cryptocurrency prices: 1-2 minutes (more volatile)
- Currency exchange rates: 1 hour (less volatile)
- Company fundamentals: 24 hours (rarely changes)
- Historical data: 24 hours (doesn't change)

---

## Error Handling and Fallbacks

**Robust Financial Data Handler:**
```python
class RobustFinancialHandler:
    def __init__(self, primary_client, backup_client=None, cache=None):
        self.primary = primary_client
        self.backup = backup_client
        self.cache = cache
    
    def get_stock_quote_with_fallback(self, symbol):
        """Get stock quote with fallback strategies"""
        
        # Try cache first
        if self.cache:
            cached = self.cache.get("stock_quote", symbol)
            if cached:
                cached["cached"] = True
                return cached
        
        # Try primary source (yfinance)
        try:
            quote = self.primary.get_quote(symbol)
            if self.cache:
                self.cache.set("stock_quote", symbol, quote, ttl_minutes=5)
            return quote
        except Exception as e:
            print(f"Primary source failed: {e}")
        
        # Try backup source (Alpha Vantage)
        if self.backup:
            try:
                quote = self.backup.get_quote(symbol)
                if self.cache:
                    self.cache.set("stock_quote", symbol, quote, ttl_minutes=5)
                quote["source"] = "backup"
                return quote
            except Exception as e:
                print(f"Backup source failed: {e}")
        
        # Return error
        return {
            "error": "Unable to retrieve stock quote",
            "symbol": symbol,
            "timestamp": datetime.now().isoformat()
        }
```

---

## Security Considerations

### API Key Management
```python
import os
from cryptography.fernet import Fernet

class SecureAPIKeyManager:
    def __init__(self, encryption_key=None):
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self.cipher = Fernet(encryption_key)
    
    def encrypt_key(self, api_key):
        """Encrypt API key"""
        return self.cipher.encrypt(api_key.encode()).decode()
    
    def decrypt_key(self, encrypted_key):
        """Decrypt API key"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def store_key(self, service_name, api_key):
        """Store encrypted API key"""
        encrypted = self.encrypt_key(api_key)
        # Store in database or secure storage
        return encrypted
    
    def retrieve_key(self, service_name):
        """Retrieve and decrypt API key"""
        # Retrieve from database or secure storage
        encrypted_key = self._get_from_storage(service_name)
        return self.decrypt_key(encrypted_key)
```

### Rate Limiting
```python
import time
from collections import deque

class APIRateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}
    
    def allow_request(self, api_name):
        """Check if request is allowed for specific API"""
        if api_name not in self.requests:
            self.requests[api_name] = deque()
        
        now = time.time()
        request_queue = self.requests[api_name]
        
        # Remove old requests
        while request_queue and request_queue[0] < now - self.time_window:
            request_queue.popleft()
        
        # Check limit
        if len(request_queue) < self.max_requests:
            request_queue.append(now)
            return True
        
        return False
    
    def wait_if_needed(self, api_name):
        """Wait if rate limit exceeded"""
        while not self.allow_request(api_name):
            time.sleep(0.5)
```

---

## Testing Strategy

**Unit Tests:**
```python
import unittest
from unittest.mock import Mock, patch

class TestFinancialDataSystem(unittest.TestCase):
    def setUp(self):
        self.financial_system = FinancialDataSystem()
    
    @patch('yfinance.Ticker')
    def test_get_stock_quote(self, mock_ticker):
        """Test stock quote retrieval"""
        # Mock yfinance response
        mock_ticker.return_value.info = {
            "currentPrice": 150.00,
            "regularMarketChangePercent": 2.5,
            "longName": "Apple Inc."
        }
        
        quote = self.financial_system.get_stock_quote("AAPL")
        
        self.assertEqual(quote["price"], 150.00)
        self.assertEqual(quote["change_percent"], 2.5)
    
    def test_currency_conversion(self):
        """Test currency conversion"""
        conversion = self.financial_system.convert_currency(100, "USD", "EUR")
        
        self.assertIn("converted_amount", conversion)
        self.assertIn("rate", conversion)
        self.assertEqual(conversion["from"], "USD")
        self.assertEqual(conversion["to"], "EUR")
    
    def test_portfolio_calculation(self):
        """Test portfolio value calculation"""
        portfolio = {
            "stocks": {"AAPL": 10},
            "cash": {"USD": 1000}
        }
        
        result = self.financial_system.get_portfolio_value(portfolio)
        
        self.assertIn("total_value_usd", result)
        self.assertIn("details", result)
        self.assertGreater(result["total_value_usd"], 1000)
```

**Integration Tests:**
```bash
# Test yfinance
python -c "
import yfinance as yf
ticker = yf.Ticker('AAPL')
price = ticker.info.get('currentPrice')
print(f'AAPL: ${price}')
assert price is not None
"

# Test Frankfurter API
curl https://api.frankfurter.app/latest?from=USD&to=EUR

# Test CoinGecko API
curl "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
```

---

## Cost Analysis

| Component | Setup Cost | Ongoing Cost | Rate Limits | Notes |
|-----------|------------|--------------|-------------|-------|
| yfinance | $0 | $0 | ~2000 req/hour | Unofficial, may break |
| Frankfurter API | $0 | $0 | None | Free, ECB data |
| CoinGecko Demo | $0 | $0 | 10-30 calls/min | Free tier, no credit card |
| Alpha Vantage Free | $0 | $0 | 25 req/day | Very limited |
| Alpha Vantage Premium | $0 | $49.99/month | 500 req/day | Optional upgrade |
| ExchangeRate-API Free | $0 | $0 | 1500 req/month | More currencies |

**Total Estimated Cost (Basic Setup):** $0/month
**Total Estimated Cost (With Premium APIs):** $50-100/month (optional)

---

## Conclusion

For PASSFEL's financial information capabilities (#4), the recommended implementation approach is:

1. **Start with yfinance** for stock market data (free, comprehensive, no API key)
2. **Use Frankfurter API** for currency exchange rates (free, reliable, ECB data)
3. **Add CoinGecko Demo API** for cryptocurrency prices (free tier, 10-30 calls/min)
4. **Implement caching system** using existing PostgreSQL infrastructure
5. **Add portfolio tracking** for multi-asset monitoring
6. **Consider Alpha Vantage** as backup for yfinance (optional, free tier limited)
7. **Implement rate limiting** and error handling for reliability

This phased approach provides comprehensive financial data capabilities while minimizing costs and maintaining reliability. The system can track stocks, cryptocurrencies, and currency exchange rates with proper caching and fallback strategies for robustness.

---

*Last Updated: 2025-01-29*
*Research conducted for PASSFEL project feature #4 (Financial Information) by Devin*
