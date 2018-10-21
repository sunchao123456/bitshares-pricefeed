# pylint: disable=no-member
from . import FeedSource, fetch_all
from operator import itemgetter
import itertools
import statistics
import numpy as num
import logging
log = logging.getLogger(__name__)

class Composite(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert hasattr(self, "aggregation_type"), "Composite needs 'aggregation_type'"
        valid_aggregation_types = ['min', 'max', 'mean', 'median', 'weighted_mean', 'first_valid']
        assert getattr(self, "aggregation_type") in valid_aggregation_types, "Composite needs 'aggregation_type' to be one of {}".format(valid_aggregation_types)
        if self.aggregation_type == 'first':
            assert hasattr(self, "order"), "Composite needs an 'order' of source when 'first_valid' aggregation type is selected"
        assert hasattr(self, "exchanges"), "Composite needs 'exchanges'"

    def _extract_assets(self, feed):
        quotes = [ source.keys() for source in feed.values() ]
        quotes = set(itertools.chain.from_iterable(quotes)) # Flatten + uniq
        # Remove special 'response' key.
        if 'response' in quotes:
            quotes.remove('response')

        bases = []
        for source in feed.values():
            for quote in quotes:
                if quote in source:
                    bases.append(source[quote].keys())
        bases = set(itertools.chain.from_iterable(bases)) # Flatten + uniq
        
        return (bases, quotes)

    def _extract_feeds(self, base, quote, feeds):
        extracted_feeds = []
        for source, data in feeds.items():
            if quote in data and base in data[quote]:
                data[quote][base]['source'] = source
                extracted_feeds.append(data[quote][base])
        return extracted_feeds

    def _select_feed(self, feeds):
        # pylint: disable=no-member
        if self.aggregation_type == 'min':
            return min(feeds, key=itemgetter('price'))
        elif self.aggregation_type == 'max':
            return max(feeds, key=itemgetter('price'))
        elif self.aggregation_type == 'median': 
            return {
                'price': statistics.median(x['price'] for x in feeds),
                'volume': sum( x['volume'] for x in feeds ),
                'source': 'median({})'.format(', '.join([x['source'] for x in feeds]))
            }
        elif self.aggregation_type == 'mean': 
            return {
                'price': statistics.mean(x['price'] for x in feeds),
                'volume': sum(x['volume'] for x in feeds),
                'source': 'mean({})'.format(', '.join([x['source'] for x in feeds]))
            }
        elif self.aggregation_type == 'weighted_mean':
            return {
                'price': num.average([x['price'] for x in feeds], weights = [x['volume'] for x in feeds]),
                'volume': sum(x['volume'] for x in feeds),
                'source': 'weighted_mean({})'.format(', '.join([x['source'] for x in feeds]))
            }
        elif self.aggregation_type == 'first_valid':
            for source in self.order:
                found = next((feed for feed in feeds if feed['source'] == source), None)
                if found:
                    return found                

    def _filter(self, feed):
        bases, quotes = self._extract_assets(feed)
        filtered_feed = {}
        for quote in quotes:
            filtered_feed[quote] = {}
            for base in bases:
                extracted_feeds = self._extract_feeds(base, quote, feed)
                filtered_feed[quote][base] = self._select_feed(extracted_feeds)
        return filtered_feed

    def _fetch(self):
        feed = fetch_all(self.exchanges)
        result = self._filter(feed)
        return result

