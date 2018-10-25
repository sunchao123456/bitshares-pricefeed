import requests
from . import FeedSource, _request_headers

class Coinbase(FeedSource):
    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue

                pair = '{}-{}'.format(quote.upper(), base.upper())
                url = "https://api.pro.coinbase.com/products/{}/ticker".format(pair)
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                if response.status_code != requests.codes.ok: # pylint: disable=no-member
                    print('No result on Coinbase for {}'.format(pair))
                    continue
                result = response.json()
                self.add_rate(feed, base, quote, float(result['price']), float(result['volume']))
        return feed