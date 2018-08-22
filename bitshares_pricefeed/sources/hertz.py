from datetime import datetime
import math
from . import FeedSource

SECONDS_PER_DAY = 60 * 60 * 24

class Hertz(FeedSource):

    def _compute_hertz(self, reference_timestamp, current_timestamp, period_days, phase_days, reference_asset_value, amplitude):
        hz_reference_timestamp = datetime.strptime(reference_timestamp, "%Y-%m-%dT%H:%M:%S").timestamp()
        hz_period = SECONDS_PER_DAY * period_days
        hz_phase = SECONDS_PER_DAY * phase_days
        hz_waveform = math.sin(((((current_timestamp - (hz_reference_timestamp + hz_phase))/hz_period) % 1) * hz_period) * ((2*math.pi)/hz_period)) # Only change for an alternative HERTZ ABA.
        hz_value = reference_asset_value + ((amplitude * reference_asset_value) * hz_waveform)
        return hz_value
    
    def _fetch(self):
        feed = {}
        hertz_reference_timestamp = "2015-10-13T14:12:24" # Bitshares 2.0 genesis block timestamp
        hertz_current_timestamp = datetime.now().timestamp() # Current timestamp for reference within the hertz script
        hertz_amplitude = 0.14 # 14% fluctuating the price feed $+-0.14 (2% per day)
        hertz_period_days = 28 # Aka wavelength, time for one full SIN wave cycle.
        hertz_phase_days = 0.908056 # Time offset from genesis till the first wednesday, to set wednesday as the primary Hz day.
        hertz_reference_asset_value = 1.00 # $1.00 USD, not much point changing as the ratio will be the same.

        # Calculate the current value of Hertz in USD
        hertz_value = self._compute_hertz(hertz_reference_timestamp, hertz_current_timestamp, hertz_period_days, hertz_phase_days, hertz_reference_asset_value, hertz_amplitude)

        self.add_rate(feed, 'USD', 'HERTZ', hertz_value, 1.0)
        return feed
