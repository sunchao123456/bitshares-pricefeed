import csv
import json
import requests
from . import FeedSource, _request_headers


class Graphene(FeedSource):
    def _fetch(self):
        from bitshares.market import Market
        feed = {}
        try:
            for base in self.bases:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    ticker = Market("%s:%s" % (quote, base)).ticker()
                    if (float(ticker["latest"])) > 0 and float(ticker["quoteVolume"]) > 0:
                        self.add_rate(feed, base, quote, float(ticker["latest"]), float(ticker["quoteVolume"]))
        except Exception as e:
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed
