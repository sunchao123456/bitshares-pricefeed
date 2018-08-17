import requests
from . import FeedSource, _request_headers

class CoinTiger(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://www.cointiger.com/exchange/api/public/market/detail"
        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()

        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                pair = '{}{}'.format(quote, base)
                if pair in result:
                    # USe baseVolume for volume as it seems that cointiger invert quote and base.
                    self.add_rate(feed, base, quote, float(result[pair]['last']), float(result[pair]["baseVolume"]))
                else:
                    pair = '{}{}'.format(base, quote)
                    if pair in result:
                        self.add_rate(feed, base, quote, 1/float(result[pair]['last']), float(result[pair]["quoteVolume"]))
        return feed
