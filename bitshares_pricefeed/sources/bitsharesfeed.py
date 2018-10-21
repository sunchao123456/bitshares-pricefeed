import requests
from . import FeedSource, _request_headers


# pylint: disable=no-member
class BitsharesFeed(FeedSource):
    def _fetch(self):
        from bitshares.asset import Asset
        feed = {}
        for assetName in self.assets:
            asset = Asset(assetName, full=True)
            currentPrice = asset.feed['settlement_price']
            (base, quote) = currentPrice.symbols()
            self.add_rate(feed, base, quote, currentPrice['price'], 1.0)
        return feed
