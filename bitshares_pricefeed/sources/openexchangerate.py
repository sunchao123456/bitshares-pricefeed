import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class OpenExchangeRates(FeedSource):  # Hourly updated data with free subscription
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "api_key") or not hasattr(self, "free_subscription"):
            raise Exception("OpenExchangeRates FeedSource requires 'api_key' and 'free_subscription'")

    def _fetch(self):
        feed = {}
        for base in self.bases:
            url = "https://openexchangerates.org/api/latest.json?app_id=%s&base=%s" % (self.api_key, base)
            if self.free_subscription and base != 'USD':
                continue
            response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
            result = response.json()
            if result.get("base") != base:
                raise Exception("Error fetching from url. Returned: {}".format(result))
            for quote in self.quotes:
                if quote == base:
                    continue
                self.add_rate(feed, base, quote,  1 / result["rates"][quote], 1.0)
        return feed
