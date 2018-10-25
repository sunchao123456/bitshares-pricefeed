import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class RobinHood(FeedSource): # Stocks prices from RobinHood: https://github.com/sanko/Robinhood
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
        url = "https://api.robinhood.com/quotes/?symbols={symbols}"
        for base in symbols_by_base.keys():
            response = requests.get(url=url.format(
                symbols=','.join(symbols_by_base[base])
            ), headers=_request_headers, timeout=self.timeout)
            result = response.json()['results']
            for ticker in result:
                self.add_rate(feed, base, ticker['symbol'], float(ticker["last_trade_price"]), 1.0)
        return feed