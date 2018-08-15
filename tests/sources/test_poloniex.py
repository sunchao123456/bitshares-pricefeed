from bitshares_pricefeed.sources.poloniex import Poloniex, PoloniexVWAP
import unittest 

def test_poloniex_fetch(checkers):
    source = Poloniex(quotes=['BTS', 'ETH'], bases=['BTC']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'ETH:BTC'])

def test_poloniex_vwap_fetch(checkers):
    source = PoloniexVWAP(quotes=['BTS', 'ETH'], bases=['BTC']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BTS:BTC', 'ETH:BTC'])

