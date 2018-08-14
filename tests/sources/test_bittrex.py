from bitshares_pricefeed.sources.bittrex import Bittrex

def test_bittrex_fetch(checkers):
    source = Bittrex(quotes=['BTC'], bases=['USDT'], aliases={ 'USDT': 'USD'} ) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:USD'])


