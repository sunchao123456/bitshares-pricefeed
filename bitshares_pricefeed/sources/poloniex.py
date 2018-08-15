import requests
from datetime import timedelta, datetime
from . import FeedSource, _request_headers


class Poloniex(FeedSource):
    def _fetch(self):
        feed = {}
        url = "https://poloniex.com/public?command=returnTicker"
        response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
        result = response.json()
        feed["response"] = result
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                marketName = base + "_" + quote
                if marketName in result:
                    self.add_rate(feed, base, quote, float(result[marketName]["last"]), float(result[marketName]["quoteVolume"]))
        return feed

class PoloniexVWAP(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.period = getattr(self, "period", 900)

    def _fetch(self):
        feed = {}
        start_date = datetime.utcnow() - timedelta(hours=1)
        for base in self.bases:
            for quote in self.quotes:
                if quote == base:
                    continue
                url = "https://poloniex.com/public?command=returnChartData&currencyPair={}_{}&start={}&end=9999999999&period={}".format(base, quote, start_date.timestamp(), self.period)
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                result = response.json()
                vwap = result[-1]
                self.add_rate(feed, base, quote, vwap["weightedAverage"], vwap["quoteVolume"])
        return feed
