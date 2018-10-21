import datetime
import requests
from . import FeedSource, _request_headers
import quandl

# pylint: disable=no-member
class Quandl(FeedSource):  # Quandl using Python API client
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxAge = getattr(self, "maxAge", 5)

        quandl.ApiConfig.api_key = self.api_key
        quandl.ApiConfig.api_version = '2015-04-09'

    def _fetch(self):
        feed = {}
        for market in self.datasets:
            quote, base = market.split(":")
            for dataset in self.datasets[market]:
                data = quandl.get(dataset, rows=1, returns='numpy')
            self.add_rate(feed, base, quote, data[0][1], 1.0)
        return feed


class QuandlPlain(FeedSource):  # Quandl direct HTTP
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.maxAge = getattr(self, "maxAge", 5)

    def _fetch(self):
        feed = {}

        for market in self.datasets:
            quote, base = market.split(":")
            prices = []
            for dataset in self.datasets[market]:
                url = "https://www.quandl.com/api/v3/datasets/{dataset}.json?start_date={date}".format(
                    dataset=dataset,
                    date=datetime.datetime.strftime(datetime.datetime.now() -
                                                    datetime.timedelta(days=self.maxAge),
                                                    "%Y-%m-%d")
                )
                if hasattr(self, "api_key"):
                    url += "&api_key=%s" % self.api_key
                response = requests.get(url=url, headers=_request_headers, timeout=self.timeout)
                data = response.json()
                if "quandl_error" in data:
                    raise Exception(data["quandl_error"]["message"])
                if "dataset" not in data:
                    raise Exception("Feed has not returned a dataset for url: %s" % url)
                d = data["dataset"]
                if len(d["data"]):
                    prices.append(d["data"][0][1])
            self.add_rate(feed, base, quote, sum(prices) / len(prices), 1.0)
        return feed
