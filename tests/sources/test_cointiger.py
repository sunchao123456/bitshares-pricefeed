from bitshares_pricefeed.sources.cointiger import CoinTiger

def test_cointiger_fetch(checkers):
    source = CoinTiger(quotes=['BTS', 'BITCNY', 'FAKE'], bases=['BTC', 'ETH']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'BTS:ETH', 'BITCNY:BTC', 'BITCNY:ETH'])