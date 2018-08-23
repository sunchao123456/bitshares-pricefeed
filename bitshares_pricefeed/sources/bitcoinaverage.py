import requests
from . import FeedSource, _request_headers

class BitcoinAverage(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.symbol_set = getattr(self, "symbol_set", 'local')
        valid_symbol_sets = ['global', 'local', 'crypto', 'tokens']
        assert self.symbol_set in valid_symbol_sets, "BitcoinAverage needs 'symbol_set' to be one of {}".format(valid_symbol_sets)

    def _fetch(self):
        feed = {}
        url = "https://apiv2.bitcoinaverage.com/indices/{}/ticker/{}{}"
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                endpoint = url.format(self.symbol_set, quote, base)
                response = requests.get(url=endpoint, headers=_request_headers, timeout=self.timeout)
                if response.status_code == 200:
                    result = response.json()
                    self.add_rate(feed, base, quote, result["last"], result["volume"] * result['last'])
        return feed
