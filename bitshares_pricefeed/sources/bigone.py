import requests
from . import FeedSource, _request_headers


class BigONE(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://big.one/api/v2/tickers"
        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()
        for ticker in result["data"]:
            for base in self.bases:
                for quote in self.quotes:
                    if base == quote:
                        continue
                    if ticker['market_id'] == "{}-{}".format(quote.upper(), base.upper()):
                        price = (float(ticker['bid']['price']) + float(ticker['ask']['price'])) / 2
                        volume = float(ticker['volume']) if ticker['volume'] else 0
                        self.add_rate(feed, base, quote, price, volume)
        return feed
