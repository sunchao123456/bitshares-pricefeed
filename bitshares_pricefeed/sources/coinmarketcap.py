import requests
from . import FeedSource, _request_headers


class Coinmarketcap(FeedSource):
    def _fetch(self):
        feed = {}
        url = 'https://api.coinmarketcap.com/v1/ticker/'
        response = requests.get(
            url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()
        for asset in result:
            for quote in self.quotes:
                if asset["symbol"] == quote:
                    
                    self.add_rate(feed, 'BTC', quote, 
                        float(asset["price_btc"]), 
                        float(asset["24h_volume_usd"]) / float(asset["price_btc"]))

                    self.add_rate(feed, 'USD', quote, float(asset["price_usd"]), float(asset["24h_volume_usd"]))
        self._fetch_altcap(feed)

        return feed

    def _fetch_altcap(self, feed):
        if 'BTC' in self.bases and ('ALTCAP' in self.quotes or 'ALTCAP.X' in self.quotes):
            ticker = requests.get(
                'https://api.coinmarketcap.com/v1/ticker/').json()
            global_data = requests.get(
                'https://api.coinmarketcap.com/v1/global/').json()
            bitcoin_data = requests.get(
                'https://api.coinmarketcap.com/v1/ticker/bitcoin/'
            ).json()[0]
            alt_caps_x = [float(coin['market_cap_usd'])
                            for coin in ticker if
                            float(coin['rank']) <= 11 and
                            coin['symbol'] != "BTC"
                            ]
            alt_cap = (
                float(global_data['total_market_cap_usd']) -
                float(bitcoin_data['market_cap_usd']))
            alt_cap_x = sum(alt_caps_x)
            btc_cap = next((
                coin['market_cap_usd']
                for coin in ticker if coin["symbol"] == "BTC"))

            btc_altcap_price = float(alt_cap) / float(btc_cap)
            btc_altcapx_price = float(alt_cap_x) / float(btc_cap)

            if 'ALTCAP' in self.quotes:
                self.add_rate(feed, 'BTC', 'ALTCAP', btc_altcap_price, 1.0)
            if 'ALTCAP.X' in self.quotes:
                self.add_rate(feed, 'BTC', 'ALTCAP.X', btc_altcapx_price, 1.0)
        return feed

class CoinmarketcapPro(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, 'api_key'):
            raise Exception("CoinmarketcapPro FeedSource requires 'api_key'.")

    def _fetch(self):
        feed = {}
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest?symbol={}&convert={}'
        headers = { **_request_headers, 'X-CMC_PRO_API_KEY': self.api_key } # pylint: disable=no-member
        all_quotes = ','.join(self.quotes)
        for base in self.bases:
            response = requests.get(url=url.format(all_quotes, base), headers=headers, timeout=self.timeout)
            result = response.json()
            for quote, ticker in result['data'].items():
                price = ticker['quote'][base]['price']
                volume = ticker['quote'][base]['volume_24h'] / price
                self.add_rate(feed, base, quote, price, volume)

        return feed