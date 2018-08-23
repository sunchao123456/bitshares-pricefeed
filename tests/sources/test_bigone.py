from bitshares_pricefeed.sources.bigone import BigONE

def test_bigone_fetch(checkers):
    source = BigONE(quotes=['BTC', 'BTS'], bases=['USDT', 'BTC']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'BTC:USDT'])


