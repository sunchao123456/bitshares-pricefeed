import requests
from . import FeedSource, _request_headers


class Bittrex(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://bittrex.com/api/v1.1/public/getmarketsummaries"
        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()["result"]
        feed["response"] = response.json()
        for thisMarket in result:
            for base in self.bases:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    if thisMarket["MarketName"] == base + "-" + quote:
                        self.add_rate(feed, base, quote, float(thisMarket["Last"]), float(thisMarket["Volume"]))
        return feed
