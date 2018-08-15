import requests
from . import FeedSource, _request_headers


class Bitstamp(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://www.bitstamp.net/api/v2/ticker/{quote}{base}"
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                # btcusd, btceur
                response = requests.get(url=url.format(
                    quote=quote.lower(),
                    base=base.lower()
                ), headers=_request_headers, timeout=self.timeout)
                result = response.json()
                self.add_rate(feed, base, quote, float(result["last"]), float(result["volume"]))
        return feed
