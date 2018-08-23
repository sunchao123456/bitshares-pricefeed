import requests
from . import FeedSource, _request_headers


class IndoDax(FeedSource):
    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                url = "https://indodax.com/api/%s_%s/ticker" % (quote.lower(), base.lower())
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                result = response.json()
                if response.status_code != 200 or 'error' in result:
                    print("\nFetched data from {0} has error for pair {2}/{3}: {1}!".format(type(self).__name__, result['error_description'], quote, base))
                    continue

                ticker = result["ticker"]
                self.add_rate(feed, base, quote, float(ticker["last"]), float(ticker["vol_" + quote.lower()]))
                feed[self.alias(base)]["response"] = result
        return feed
