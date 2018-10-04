import requests
from . import FeedSource, _request_headers


class Kraken(FeedSource):
    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue

                pair = '{}{}'.format(quote.upper(), base.upper())
                url = "https://api.kraken.com/0/public/Ticker?pair={}".format(pair)
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                if response.status_code != requests.codes.ok:
                    print('No result on Kraken for {}'.format(pair))
                    continue
                result = response.json()['result'][pair]
                self.add_rate(feed, base, quote, float(result['c'][0]), float(result['v'][1]))
        
        return feed

