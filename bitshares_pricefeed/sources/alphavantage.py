import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class AlphaVantage(FeedSource):  # Alpha Vantage
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout = getattr(self, 'timeout', 15)
        if not hasattr(self, "api_key"):
            raise Exception("AlphaVantage FeedSource requires an 'api_key'.")

    def _fetchForex(self, feed):
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                url = (
                    'https://www.alphavantage.co/query'
                    '?function=CURRENCY_EXCHANGE_RATE&from_currency={quote}&to_currency={base}&apikey={apikey}'
                ).format(base=base, quote=quote, apikey=self.api_key)
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                result = response.json()
                price = float(result['Realtime Currency Exchange Rate']['5. Exchange Rate'])
                self.add_rate(feed, base, quote, price, 1.0)
        return feed


    def _fetchEquities(self, feed):
        if not hasattr(self, "equities") or len(self.equities) == 0:
            return feed

        symbols = ",".join([ equity.split(':')[0] for equity in self.equities ])
        url = (
            'https://www.alphavantage.co/query'
            '?function=BATCH_STOCK_QUOTES&symbols={symbols}&apikey={apikey}'
        ).format(symbols=symbols, apikey=self.api_key)

        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()

        for equity in self.equities:
            (name, base) = equity.split(':')
            for ticker in result['Stock Quotes']:
                if ticker['1. symbol'] == name:
                    price = float(ticker['2. price'])
                    volume = float(ticker['3. volume']) if ticker['3. volume'] != '--' else 1.0
                    self.add_rate(feed, base, name, price, volume)
        return feed


    def _fetch(self):
        feed = {}
        try:
            feed = self._fetchForex(feed)
            feed = self._fetchEquities(feed)
        except Exception as e:
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed
