from bitshares_pricefeed.sources.indodax import IndoDax

def test_indodax_fetch(checkers):
    source = IndoDax(quotes=['BTC', 'BTS'], bases=['IDR', 'USD']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:IDR', 'BTS:IDR'])


