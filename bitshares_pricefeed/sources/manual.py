from . import FeedSource

# pylint: disable=no-member
class Manual(FeedSource):
    def _fetch(self):
        return self.feed
