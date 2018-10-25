import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class Iex(FeedSource): # Stocks prices from iextrading.com
    def _extract_symbols(self):
        symbols_by_base = {}
        for equity in self.equities:
            (symbol, base) = equity.split(':')
            if base not in symbols_by_base:
                symbols_by_base[base] = []
            symbols_by_base[base].append(symbol)
        return symbols_by_base

    def _fetch(self):
        symbols_by_base = self._extract_symbols()
        feed = {}
        url = "https://api.iextrading.com/1.0/stock/market/batch?symbols={symbols}&types=quote"
        for base in symbols_by_base.keys():
            response = requests.get(url=url.format(
                symbols=','.join(symbols_by_base[base])
            ), headers=_request_headers, timeout=self.timeout)
            result = response.json()
            for symbol in result.keys():
                ticker = result[symbol]['quote']
                self.add_rate(feed, base, symbol, float(ticker["latestPrice"]), float(ticker["latestVolume"]))
        return feed