from bitshares_pricefeed.sources.bitcoinaverage import BitcoinAverage

def test_bitcoinaverage_fetch(checkers):
    source = BitcoinAverage(quotes=['BTC', 'USDT'], bases=['EUR', 'USD']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:USD', 'BTC:EUR', 'USDT:USD'])


