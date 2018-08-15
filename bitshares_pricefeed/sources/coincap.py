import requests
from . import FeedSource, _request_headers


class Coincap(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.nb_coins_included_in_altcap_x = getattr(self, 'nb_coins_included_in_altcap_x', 10)

    def _fetch(self):
        feed = {}
        base = self.bases[0]
        if base == 'BTC':
            coincap_front = requests.get('http://www.coincap.io/front').json()
            coincap_global = requests.get('http://www.coincap.io/global').json()
            alt_cap = float(coincap_global["altCap"])
            alt_caps_x = [float(coin['mktcap'])
                            for coin in coincap_front[0:self.nb_coins_included_in_altcap_x+1]
                            if coin['short'] != "BTC"][0:self.nb_coins_included_in_altcap_x]
            alt_cap_x = sum(alt_caps_x)
            btc_cap = float(coincap_global["btcCap"])

            btc_altcap_price = alt_cap / btc_cap
            btc_altcapx_price = alt_cap_x / btc_cap

            if 'ALTCAP' in self.quotes:
                self.add_rate(feed, base, 'ALTCAP', btc_altcap_price, 1.0)
            if 'ALTCAP.X' in self.quotes:
                self.add_rate(feed, base, 'ALTCAP.X', btc_altcapx_price, 1.0)
        return feed

