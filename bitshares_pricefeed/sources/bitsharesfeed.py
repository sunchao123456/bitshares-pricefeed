import requests
from . import FeedSource, _request_headers


class BitsharesFeed(FeedSource):
    def _fetch(self):
        from bitshares.asset import Asset
        feed = {}
        try:
            for assetName in self.assets:
                asset = Asset(assetName, full=True)
                currentPrice = asset.feed['settlement_price']
                (base, quote) = currentPrice.symbols()
                self.add_rate(feed, base, quote, currentPrice['price'], 1.0)
        except Exception as e:
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed
