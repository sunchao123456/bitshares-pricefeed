from . import FeedSource
from bitcoinaverage import RestfulClient


class BitcoinAverage(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert hasattr(self, "secret_key"), "Bitcoinaverage needs 'secret_key'"
        assert hasattr(self, "public_key"), "Bitcoinaverage needs 'public_key'"
        self.rest = RestfulClient(self.secret_key, self.public_key)

    def _fetch(self):
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                result = self.rest.ticker_global_per_symbol(
                    quote.upper() + base.upper()
                )
                self.add_rate(feed, base, quote, float(result["last"]), float(result["volume"]))
        return feed
