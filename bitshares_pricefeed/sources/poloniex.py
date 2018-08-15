import requests
from datetime import timedelta, datetime
from . import FeedSource, _request_headers


class Poloniex(FeedSource):
    def _fetch(self):
        feed = {}
        try:
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
        except Exception as e:
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed

class PoloniexVWAP(FeedSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.period = getattr(self, "period", 900)

    def _fetch(self):
        feed = {}
        try:
            start_date = datetime.utcnow() - timedelta(hours=1)
            for base in self.bases:
                for quote in self.quotes:
                    if quote == base:
                        continue
                    url = "https://poloniex.com/public?command=returnChartData&currencyPair={}_{}&start={}&end=9999999999&period={}".format(base, quote, start_date.timestamp(), self.period)
                    print(url)
                    response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                    result = response.json()
                    print(result)
                    vwap = result[-1]
                    self.add_rate(feed, base, quote, vwap["weightedAverage"], vwap["quoteVolume"])
        except Exception as e:
            import traceback, sys
            traceback.print_exc(file=sys.stdout)
            raise Exception("\nError fetching results from {1}! ({0})".format(str(e), type(self).__name__))
        return feed
