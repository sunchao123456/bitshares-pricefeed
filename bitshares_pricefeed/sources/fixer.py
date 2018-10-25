import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class Fixer(FeedSource):  # fixer.io daily updated data from European Central Bank.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "api_key") or not hasattr(self, "free_subscription"):
            raise Exception("Fixer FeedSource requires 'api_key' and 'free_subscription'")

    def _fetch(self):
        feed = {}
        for base in self.bases:
            if self.free_subscription and base != 'EUR':
                continue
            url = "http://data.fixer.io/api/latest?access_key=%s&base=%s" % (self.api_key, base)
            response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
            result = response.json()
            for quote in self.quotes:
                if quote == base:
                    continue
                self.add_rate(feed, base, quote, 1.0 / float(result["rates"][quote]), 1.0)
        return feed
