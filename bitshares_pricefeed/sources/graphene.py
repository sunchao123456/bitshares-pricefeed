import requests
from . import FeedSource, _request_headers


class Graphene(FeedSource):
    def _fetch(self):
        from bitshares.market import Market
        feed = {}
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                ticker = Market("%s:%s" % (quote, base)).ticker()
                if (float(ticker["latest"])) > 0 and float(ticker["quoteVolume"]) > 0:
                    self.add_rate(feed, base, quote, float(ticker["latest"]), float(ticker["quoteVolume"]))
        return feed
