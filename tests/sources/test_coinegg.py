from bitshares_pricefeed.sources.coinegg import CoinEgg

def test_coinegg_fetch(checkers):
    source = CoinEgg(quotes=['BTS', 'ETH'], bases=['BTC', 'USDT']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'ETH:BTC', 'ETH:USDT'])


