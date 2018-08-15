import requests
from . import FeedSource, _request_headers

class CoinEgg(FeedSource):
    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue

                url = "https://api.coinegg.im/api/v1/ticker/region/{}?coin={}".format(base.lower(), quote.lower())
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                result = response.json()

                if 'result' in result and result['result'] == False:
                    continue

                self.add_rate(feed, base, quote, float(result['last']), float(result["vol"]))
        return feed
