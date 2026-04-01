__all__ = ()

from decimal import Decimal

from apps.stocks.models import Stock

from django.utils import timezone

from cachetools import TTLCache

import requests


class MOEXService:
    BASE_URL = "https://iss.moex.com/iss"

    _cache = TTLCache(maxsize=1000, ttl=300)

    @classmethod
    def safe_decimal(cls, value):
        if value is None or value == "":
            return Decimal("0")

        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    @classmethod
    def get_current_quotes(cls, tickers):
        quotes = {}
        tickers_cesh = []

        for ticker in tickers:
            cached_quote = cls._cache.get(ticker)
            if cached_quote is not None:
                quotes[ticker] = cached_quote
            else:
                tickers_cesh.append(ticker)
        if tickers_cesh:
            for ticker in tickers_cesh:
                url = f"{cls.BASE_URL}/engines/stock/markets/shares/securities/{ticker}.json"

                try:
                    response = requests.get(url, timeout=10)
                    data = response.json()

                    if "marketdata" in data and data["marketdata"].get("data"):
                        columns = data["marketdata"]["columns"]
                        rows = data["marketdata"]["data"]

                        for row in rows:
                            board = row[1] if len(row) > 1 else ""
                            if board == "TQBR":
                                result = {}
                                for i, col in enumerate(columns):
                                    if i < len(row):
                                        result[col] = row[i]
                                quote_data = {
                                    "LAST": cls.safe_decimal(
                                        result.get("LAST", 0)
                                    ),
                                    "OPEN": cls.safe_decimal(
                                        result.get("OPEN", 0)
                                    ),
                                    "HIGH": cls.safe_decimal(
                                        result.get("HIGH", 0)
                                    ),
                                    "LOW": cls.safe_decimal(
                                        result.get("LOW", 0)
                                    ),
                                    "VOLUME": result.get("QTY", 0) or 0,
                                    "VALUE": cls.safe_decimal(
                                        result.get("VALUE", 0)
                                    ),
                                    "CHANGE": cls.safe_decimal(
                                        result.get("CHANGE", 0)
                                    ),
                                    "CHANGEPERCENT": cls.safe_decimal(
                                        result.get("LASTCHANGEPRCNT", 0)
                                    ),
                                }
                                cls._cache[ticker] = quote_data

                                quotes[ticker] = quote_data
                                break

                        if ticker not in quotes:
                            quotes[ticker] = None
                    else:
                        quotes[ticker] = None

                except Exception:
                    quotes[ticker] = None

        return quotes

    @classmethod
    def update_all_stocks(cls):
        stocks = Stock.objects.all()
        if not stocks.exists():
            return 0

        tickers = list(stocks.values_list("ticker", flat=True))

        quotes = cls.get_current_quotes(tickers)

        updated_count = 0
        for stock in stocks:
            quote = quotes.get(stock.ticker)
            if quote and quote["LAST"] > 0:
                stock.last_price = quote["LAST"]
                stock.open_price = quote.get("OPEN", stock.open_price)
                stock.high_price = quote.get("HIGH", stock.high_price)
                stock.low_price = quote.get("LOW", stock.low_price)
                stock.volume = quote.get("VOLUME", stock.volume)
                stock.value = quote.get("VALUE", stock.value)
                stock.change = quote.get("CHANGE", stock.change)
                stock.change_percent = quote.get(
                    "CHANGEPERCENT",
                    stock.change_percent,
                )
                stock.last_price_updated = timezone.now()
                stock.save()
                updated_count += 1

        return updated_count

    @classmethod
    def update_single_stock(cls, ticker):
        try:
            stock = Stock.objects.get(ticker=ticker)
            quotes = cls.get_current_quotes([ticker])

            if quotes and quotes.get(ticker):
                quote = quotes[ticker]
                if quote and quote["LAST"] > 0:
                    stock.last_price = quote["LAST"]
                    stock.open_price = quote.get("OPEN", stock.open_price)
                    stock.high_price = quote.get("HIGH", stock.high_price)
                    stock.low_price = quote.get("LOW", stock.low_price)
                    stock.volume = quote.get("VOLUME", stock.volume)
                    stock.value = quote.get("VALUE", stock.value)
                    stock.change = quote.get("CHANGE", stock.change)
                    stock.change_percent = quote.get(
                        "CHANGEPERCENT",
                        stock.change_percent,
                    )
                    stock.last_price_updated = timezone.now()
                    stock.save()
                    return stock

        except Stock.DoesNotExist:
            pass

        return None

    @classmethod
    def get_cache_stats(cls):
        return {
            "cache_size": len(cls._cache),
            "cached_tickers": list(cls._cache.keys()),
            "ttl_seconds": cls._cache.ttl,
        }
