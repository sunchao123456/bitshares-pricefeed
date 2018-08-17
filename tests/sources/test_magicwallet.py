import os
import pytest
from bitshares_pricefeed.sources.magicwallet import MagicWallet

def test_magicwallet_support_only_cny_pair(checkers):
    with pytest.raises(Exception):
        source = MagicWallet(quotes=['BITCNY', 'BITUSD'], bases=['CNY'], api_key=os.environ['MAGICWALLET_APIKEY']) 
        feed = source._fetch()

def test_magicwallet_default_to_cny(checkers):
    source = MagicWallet(api_key=os.environ['MAGICWALLET_APIKEY']) 
    feed = source.fetch()
    checkers.check_feed(feed, ['BITCNY:CNY'])
