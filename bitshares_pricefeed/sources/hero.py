from datetime import date
from . import FeedSource

class Hero(FeedSource):
    def _fetch(self):
        feed = {}

        hero_reference_timestamp = date(1913, 12, 23)
        current_timestamp = date.today()
        hero_days_in_year = 365.2425
        hero_inflation_rate = 1.05
        hero_value = hero_inflation_rate ** ((current_timestamp - hero_reference_timestamp).days / hero_days_in_year)

        self.add_rate(feed, 'USD', 'HERO', hero_value, 1.0)
        return feed
