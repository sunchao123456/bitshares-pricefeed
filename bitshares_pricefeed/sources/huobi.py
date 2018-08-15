import requests
from . import FeedSource, _request_headers


class Huobi(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://api.huobi.pro/market/tickers"
        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()
        if result['status'] == 'error':
            raise Exception(result['err-msg'])
        for ticker in result['data']:
            for base in self.bases:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    if ticker['symbol'] == '{}{}'.format(quote.lower(), base.lower()):
                        self.add_rate(feed, base, quote, ticker['close'], ticker["vol"] /ticker['close'])
        return feed
