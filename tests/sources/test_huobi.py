from bitshares_pricefeed.sources.huobi import Huobi

def test_huobi_fetch(checkers):
    source = Huobi(quotes=['BTS', 'ETH'], bases=['BTC', 'USDT']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'ETH:BTC', 'BTS:USDT', 'ETH:USDT'])


