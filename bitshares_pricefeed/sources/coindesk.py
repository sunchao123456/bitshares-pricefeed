import requests
from . import FeedSource, _request_headers


class Coindesk(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://api.coindesk.com/v1/bpi/currentprice/{base}.json"
        for base in self.bases:
            for quote in self.quotes:
                if quote != 'BTC':
                    raise Exception('Coindesk FeedSource only handle BTC quotes.')
                response = requests.get(url=url.format(
                    base=base
                ), headers=_request_headers, timeout=self.timeout)
                result = response.json()
                self.add_rate(feed, base, quote, float(result['bpi'][base]['rate_float']), 1.0)
        return feed