import sys
import requests
from . import FeedSource, _request_headers


class Okcoin(FeedSource):
    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                if base == "USD":
                    url = "https://www.okcoin.com/api/v1/ticker.do?symbol=%s_%s" % (quote.lower(), base.lower())
                elif base == "CNY":
                    url = "https://www.okcoin.cn/api/ticker.do?symbol=%s_%s" % (quote.lower(), base.lower())
                else:
                    sys.exit("\n%s does not know base type %s" % (type(self).__name__, base))
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                result = response.json()
                self.add_rate(feed, base, quote, float(result["ticker"]["last"]), float(result["ticker"]["vol"]))
                feed[self.alias(base)]["response"] = result
        return feed
