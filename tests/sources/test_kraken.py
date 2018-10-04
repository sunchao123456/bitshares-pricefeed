from bitshares_pricefeed.sources.kraken import Kraken

def test_kraken_fetch(checkers):
    source = Kraken(quotes=['USDT'], bases=['ZUSD'], aliases={ 'ZUSD': 'USD'} ) 
    feed = source.fetch()
    checkers.check_feed(feed, ['USDT:USD'])


