import requests
from . import FeedSource, _request_headers


class Poloniex(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _fetch(self):
        feed = {}
        try:
            url = "https://poloniex.com/public?command=returnTicker"
            response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
            result = response.json()
            feed["response"] = result
            for base in self.bases:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    marketName = base + "_" + quote
                    if marketName in result:
                        self.add_rate(feed, base, quote, float(result[marketName]["last"]), float(result[marketName]["quoteVolume"]))
        except Exception as e:
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed
