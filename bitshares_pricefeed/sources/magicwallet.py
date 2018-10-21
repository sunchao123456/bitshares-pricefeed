import requests
from . import FeedSource, _request_headers

# pylint: disable=no-member
class MagicWallet(FeedSource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert hasattr(self, 'api_key'), "MagicWallet feedSource requires an 'api_key'"
        self.period = getattr(self, 'period', '1h')
        self.nb_operation_threshold = getattr(self, 'nb_operation_threshold', 10)
        self.valid_periods = ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '24h']
        assert getattr(self, "period") in self.valid_periods, "MagicWallet needs 'period' to be one of {}".format(self.valid_periods)

    def _compute_rate_and_volume(self, data, period):
        for stat in data:
            if stat['datatype'] == period:
                dbitcny = float(stat['depositBitCNY'])
                wbitcny = float(stat['withdrawBitCNY'])
                dfiatcny = float(stat['depositFiatCNY'])
                wfiatcny = float(stat['withdrawFiatCNY'])
                dcount = int(stat['depositCount'])
                wcount = int(stat['withdrawCount'])
                if (dcount + wcount) == 0:
                    return (1, 0)
                return (round((dfiatcny + wfiatcny) / (dbitcny + wbitcny), 4), dcount + wcount)
        raise Exception("Invalid period {}, should be one of: {}".format(period, self.valid_periods))

    def _fetch(self):
        feed = {}
        if self.bases and ( len(self.bases) != 1 or (self.bases[0] != 'CNY' and self.bases[0] != 'BITCNY')):
            raise Exception("MagicWallet only supports BITCNY/CNY pair.")
        if self.quotes and ( len(self.quotes) != 1 or (self.quotes[0] != 'CNY' and self.quotes[0] != 'BITCNY')):
            raise Exception("MagicWallet only supports BITCNY/CNY pair.")
        
        url = 'https://redemption.icowallet.net/api_v2/RechargeAndWithdrawTables/GetListForRechargeAndWithdrawtable'
        response = requests.post(url=url, headers={ **_request_headers, 'apikey': self.api_key } , timeout=self.timeout)
        result = response.json()
        if response.status_code != 200:
            raise Exception('Error from MagicWallet API: {}'.format(result))

        rate, volume = self._compute_rate_and_volume(result, self.period)
        if volume < self.nb_operation_threshold:
            rate, volume = self._compute_rate_and_volume(result, '24h')

        self.add_rate(feed, 'CNY', 'BITCNY', rate, volume)
        return feed
