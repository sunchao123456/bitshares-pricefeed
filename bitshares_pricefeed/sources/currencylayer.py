import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class CurrencyLayer(FeedSource):  # Hourly updated data over http with free subscription
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "api_key") or not hasattr(self, "free_subscription"):
            raise Exception("CurrencyLayer FeedSource requires 'api_key' and 'free_subscription'")

    def _fetch(self):
        feed = {}
        for base in self.bases:
            url = "http://apilayer.net/api/live?access_key=%s&currencies=%s&source=%s&format=1" % (self.api_key, ",".join(self.quotes), base)
            if self.free_subscription and base != 'USD':
                continue
            response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
            result = response.json()
            if result.get("source") == base:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    self.add_rate(feed, base, quote, 1 / result["quotes"][base + quote], 1.0)
            else:
                raise Exception(result.get("description"))
        return feed
