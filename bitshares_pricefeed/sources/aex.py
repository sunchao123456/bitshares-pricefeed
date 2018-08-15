import requests
from . import FeedSource, _request_headers


class Aex(FeedSource):
    def _fetch(self):
        feed = {}
        url = "http://api.aex.com/ticker.php"
        for base in self.bases:
            for quote in self.quotes:
                if base == quote:
                    continue
                params = {'c': quote.lower(), 'mk_type': base.lower()}
                response = requests.get(url=url, params=params, headers=_request_headers, timeout=self.timeout)
                result = response.json()
                if result != None and \
                    "ticker" in result and \
                    "last" in result["ticker"] and \
                    "vol" in result["ticker"]:
                    self.add_rate(feed, base, quote, float(result["ticker"]["last"]), float(result["ticker"]["vol"]))
                else:
                    print("\nFetched data from {0} is empty!".format(type(self).__name__))
                    continue
        return feed
