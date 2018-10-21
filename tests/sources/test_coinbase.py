from bitshares_pricefeed.sources.coinbase import Coinbase

def test_coinbase_fetch(checkers):
    source = Coinbase(quotes=['BTC', 'ETH', 'FAKE'], bases=['USD']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:USD', 'ETH:USD'])
