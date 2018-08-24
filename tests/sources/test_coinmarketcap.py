import os
from bitshares_pricefeed.sources.coinmarketcap import Coinmarketcap, CoinmarketcapPro

def test_coinmarketcap_fetch(checkers):
    source = Coinmarketcap(quotes=['BTC', 'BTS'], bases=['BTC', 'USD']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:USD', 'BTS:USD', 'BTS:BTC'])


def test_coinmarketcap_altcap_fetch(checkers):
    source = Coinmarketcap(quotes=['ALTCAP', 'ALTCAP.X'], bases=['BTC']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['ALTCAP:BTC', 'ALTCAP.X:BTC'])

def test_coinmarketcap_full_fetch(checkers):
    source = Coinmarketcap(quotes=['ALTCAP', 'BTS'], bases=['BTC', 'USD']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['ALTCAP:BTC', 'BTS:BTC', 'BTS:USD'])

def test_coinmarketcappro_fetch(checkers):
    source = CoinmarketcapPro(quotes=['BTC', 'BTS'], bases=['BTC', 'USD'], api_key=os.environ['COINMARKETCAP_APIKEY']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTC:USD', 'BTS:USD', 'BTS:BTC'])
