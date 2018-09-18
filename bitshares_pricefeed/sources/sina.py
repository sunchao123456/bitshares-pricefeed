import requests
from . import FeedSource, _request_headers
import re

class Sina(FeedSource):
    
    def get_query_param(self, assets):
        query_string = ','.join(
            '%s' % (self.param_s[asset]) for asset in assets)
        return query_string

    
    def _fetch(self):
        
        
        self.param_s = {}
        #assets = ["CNY", "KRW", "TRY", "SGD", "HKD", "RUB", "SEK", "NZD",
        #          "MXN", "CAD", "CHF", "AUD", "GBP", "JPY", "EUR", "ARS"]
        for asset in self.quotes:
            if asset=="GOLD":
                self.param_s["GOLD"] = "hf_XAU"
            elif asset=="SILVER":
                self.param_s["SILVER"] = "hf_XAG"
            else:
                self.param_s[asset] = "fx_s%susd" % asset.lower()
        feed = {}
        url = "http://hq.sinajs.cn/list="
        params = self.get_query_param(self.quotes)
        response = requests.get(url=url+params, headers=_request_headers, timeout=self.timeout)
        
        price_info =dict(zip(self.quotes, response.text.splitlines()))
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                pattern = re.compile(r'"(.*)"')
                data = pattern.findall(price_info[quote])[0]
                price=0
                if self.param_s[asset][:3] == "hf_":
                    price = data.split(',')[0]
                elif self.param_s[asset][:3] == "fx_":
                    price = data.split(',')[1]
                else:
                    price = data.split(',')[3]
                self.add_rate(feed, base, quote, float(price), 1.0)
        return feed 

