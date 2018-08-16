from bitshares_pricefeed.sources.composite import Composite

sample_conf = {
    'aggregation_type': None, # Should be one of: min, max, mean, median, weighted_mean, first, sum
    'exchanges': {
        'source1': {
            'klass': 'Manual',
            'feed': {
                'BTS': {
                    'USD': {
                        'price': 1,
                        'volume': 2
                    }
                }
            }
        },
        'source2': {
            'klass': 'Manual',
            'feed': {
                'BTS': {
                    'USD': {
                        'price': 2,
                        'volume': 20
                    }
                }
            }
        },
        'source3': {
            'klass': 'Manual',
            'feed': {
                'BTS': {
                    'USD': {
                        'price': 50,
                        'volume': 1
                    }
                }
            }
        }
    }
}

def test_composite_min(checkers):
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'min'
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == 1
    assert feed['BTS']['USD']['volume'] == 2
    assert feed['BTS']['USD']['source'] == 'source1'

def test_composite_max(checkers):
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'max'
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == 50
    assert feed['BTS']['USD']['volume'] == 1
    assert feed['BTS']['USD']['source'] == 'source3'

def test_composite_median(checkers):
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'median'
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == 2
    assert feed['BTS']['USD']['volume'] == 23
    assert feed['BTS']['USD']['source'] == 'median(source1, source2, source3)'

def test_composite_mean(checkers):
    import statistics
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'mean'
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == statistics.mean([1, 2, 50])
    assert feed['BTS']['USD']['volume'] == 23
    assert feed['BTS']['USD']['source'] == 'mean(source1, source2, source3)'

def test_composite_weighted_mean(checkers):
    import statistics
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'weighted_mean'
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == 4
    assert feed['BTS']['USD']['volume'] == 23
    assert feed['BTS']['USD']['source'] == 'weighted_mean(source1, source2, source3)'

def test_composite_first_valid(checkers):
    import statistics
    conf = sample_conf.copy()
    conf['aggregation_type'] = 'first_valid'
    conf['order'] = ['source2', 'source1', 'source3']
    source = Composite(**conf) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USD:BTS'])
    assert feed['BTS']['USD']['price'] == 2
    assert feed['BTS']['USD']['volume'] == 20
    assert feed['BTS']['USD']['source'] == 'source2'
