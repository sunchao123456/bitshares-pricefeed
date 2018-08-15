import requests
from . import FeedSource, _request_headers


class Binance(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://www.binance.com/api/v1/ticker/24hr?symbol={quote}{base}"
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                response = requests.get(url=url.format(
                    quote=quote,
                    base=base
                ), headers=_request_headers, timeout=self.timeout)
                result = response.json()
                if 'msg' in result and result['msg'] == 'Invalid symbol.':
                    continue
                self.add_rate(feed, base, quote, float(result["lastPrice"]), float(result["volume"]))
        return feed