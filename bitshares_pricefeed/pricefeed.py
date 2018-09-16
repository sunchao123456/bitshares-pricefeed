import statistics
import numpy as num
import time
import json
import os.path
from math import fabs, sqrt
from bitshares.instance import shared_bitshares_instance
from bitshares.account import Account
from bitshares.asset import Asset
from bitshares.price import Price
from bitshares.amount import Amount
from bitshares.market import Market
from bitshares.witness import Witness
from bitshares.exceptions import AccountDoesNotExistsException
from datetime import datetime, date, timezone
from . import sources
import logging
log = logging.getLogger(__name__)

# logging.basicConfig(level=logging.INFO)


def weighted_std(values, weights):
    """ Weighted std for statistical reasons
    """
    average = num.average(values, weights=weights)
    variance = num.average((values - average) ** 2, weights=weights)  # Fast and numerically precise
    return sqrt(variance)


class Feed(object):
    feed = {}
    price_result = {}

    def __init__(self, config):
        self.config = config
        self.reset()
        self.get_witness_activeness()
        self.getProducer()

    def getProducer(self):
        """ Get the feed producers account
        """
        self.producer = Account(self.config["producer"])

    def get_witness_activeness(self):
        """ See if producer account is an active witness
        """
        try:
            witness = Witness(self.config["producer"])
            global_properties = shared_bitshares_instance().rpc.get_global_properties()
            self.is_active_witness = bool(witness['id'] in global_properties['active_witnesses'])
        except AccountDoesNotExistsException:
            self.is_active_witness = False

    def reset(self):
        """ Reset all for-processing variables
        """
        # Do not reset feeds here!
        self.data = {}
        for base in self.config["assets"]:
            self.data[base] = {}
            for quote in self.config["assets"]:
                self.data[base][quote] = []

    def get_my_current_feed(self, asset):
        """ Obtain my own price feed for an asset
        """
        feeds = asset.feeds
        for feed in feeds:
            if feed["producer"]["id"] == self.producer["id"]:
                return feed

    def obtain_price_change(self, symbol):
        """ Store the price change to your previous feed
        """
        asset = Asset(symbol, full=True)
        price = self.price_result.get(symbol, None)
        # if not price:
        #     raise ValueError("Price for %s has not yet been derived" % symbol)
        newPrice = price["price"]
        # get my current feed
        current_feed = self.get_my_current_feed(asset)
        if current_feed and "settlement_price" in current_feed:
            oldPrice = float(current_feed["settlement_price"])
        else:
            oldPrice = float("inf")
        self.price_result[symbol]["priceChange"] = (oldPrice - newPrice) / newPrice * 100.0
        self.price_result[symbol]["current_feed"] = current_feed
        self.price_result[symbol]["global_feed"] = asset.feed

    def obtain_flags(self, symbol):
        """ This will add attributes to price_result and indicate the results
            of a couple testsin the `flags` key
        """
        # Test flags
        self.price_result[symbol]["flags"] = []

        # Check max price change
        if fabs(self.price_result[symbol]["priceChange"]) > fabs(self.assetconf(symbol, "min_change")):
            self.price_result[symbol]["flags"].append("min_change")

        # Check max price change
        if fabs(self.price_result[symbol]["priceChange"]) > fabs(self.assetconf(symbol, "warn_change")):
            self.price_result[symbol]["flags"].append("over_warn_change")

        # Check max price change
        if fabs(self.price_result[symbol]["priceChange"]) > fabs(self.assetconf(symbol, "skip_change")):
            self.price_result[symbol]["flags"].append("skip_change")
        
        # Skip if witness is not active if flag is set.
        if self.assetconf(symbol, "skip_inactive_witness", no_fail=True) and not self.is_active_witness:
            self.price_result[symbol]["flags"].append("skip_inactive_witness")

        # Feed too old
        feed_age = self.price_result[symbol]["current_feed"]["date"] if self.price_result[symbol]["current_feed"] else datetime.min.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - feed_age).total_seconds() > self.assetconf(symbol, "maxage"):
            self.price_result[symbol]["flags"].append("over_max_age")

    def get_cer(self, symbol, price):
        if self.assethasconf(symbol, "core_exchange_rate"):
            cer = self.assetconf(symbol, "core_exchange_rate")
            required = ["orientation", "factor", "ref_ticker", "ref_ticker_attribute"]
            if any([x not in cer for x in required]):
                raise ValueError(
                    "Missing one of required settings for cer: {}".format(
                        str(required)))
            ticker = Market(cer["ref_ticker"]).ticker()
            price = ticker[cer["ref_ticker_attribute"]]
            price *= cer["factor"]
            orientation = Market(cer["orientation"])
            return price.as_quote(orientation["quote"]["symbol"])
        
        return price * self.assetconf(symbol, "core_exchange_factor")


    def get_sources(self, symbol):
        sources = self.assetconf(symbol, "sources")
        if "*" in sources:
            sources = list(self.config["exchanges"].keys())
        return sources

    def fetch(self):
        """ Fetch the prices from external exchanges
        """
        if "exchanges" not in self.config or not self.config["exchanges"]:
            return
        self.feed.update(sources.fetch_all(self.config["exchanges"]))

    def assethasconf(self, symbol, parameter):
        """ Do we have symbol specific parameters?
        """
        if (
            symbol in self.config["assets"] and
            self.config["assets"][symbol] and
            parameter in self.config["assets"][symbol]
        ):
            return True
        return False

    def assetconf(self, symbol, parameter, no_fail=False):
        """ Obtain the configuration for an asset, if not present, use default
        """
        if self.assethasconf(symbol, parameter):
            return self.config["assets"][symbol][parameter]
        elif "default" in self.config and parameter in self.config["default"]:
            return self.config["default"][parameter]
        else:
            if no_fail:
                return
            raise ValueError("%s for %s not defined!" % (
                parameter,
                symbol
            ))

    def addPrice(self, base, quote, price, volume, sources=None):
        """ Add a price to the instances, temporary storage
        """
        log.info("addPrice(self, {}, {}, {}, {} (sources: {}))".format(
            base, quote, price, volume, str(sources)))
        if base not in self.data:
            self.data[base] = {}
        if quote not in self.data[base]:
            self.data[base][quote] = []

        flat_list = []
        for source in sources:
            if isinstance(source, list):
                for item in source:
                    flat_list.append(item)
            else:
                flat_list.append(source)

        self.data[base][quote].append(dict(
            price=price,
            volume=volume,
            sources=flat_list
        ))

    def get_source_description(self, datasource, base, quote, data):
        return '{} - {}:{}'.format(data['source'] if 'source' in data else datasource, base, quote)

    def appendOriginalPrices(self, symbol):
        """ Load feed data into price/volume array for processing
            This few lines solely take the data of the chosen exchanges and put
            them into price[base][quote]. Since markets are symmetric, the
            corresponding price[quote][base] is derived accordingly and the
            corresponding volume is derived at spot price
        """
        if "exchanges" not in self.config or not self.config["exchanges"]:
            return

        for datasource in self.get_sources(symbol):
            if not self.config["exchanges"][datasource].get("enable", True):
                log.info('Skip disabled source {}'.format(datasource))
                continue
            log.info("appendOriginalPrices({}) from {}".format(symbol, datasource))
            if datasource not in self.feed:
                continue
            for base in list(self.feed[datasource]):
                if base == "response":  # skip entries that store debug data
                    continue
                for quote in list(self.feed[datasource][base]):
                    if quote == "response":  # skip entries that store debug data
                        continue
                    if not base or not quote:
                        continue

                    feed_data = self.feed[datasource][base][quote]
                    # Skip markets with zero trades in the last 24h
                    if feed_data["volume"] == 0.0:
                        continue

                    # Original price/volume
                    self.addPrice(
                        base,
                        quote,
                        feed_data["price"],
                        feed_data["volume"],
                        sources=[self.get_source_description(datasource, base, quote, feed_data)]
                    )

                    if feed_data["price"] > 0 and feed_data["volume"] > 0:
                        # Inverted pair price/volume
                        self.addPrice(
                            quote,
                            base,
                            float(1.0 / feed_data["price"]),
                            float(feed_data["volume"] * feed_data["price"]),
                            sources=[self.get_source_description(datasource, quote, base, feed_data)]
                        )

    def derive2Markets(self, base_symbol, target_symbol):
        """ derive BTS prices for all assets in assets_derive
            This loop adds prices going via 2 markets:
            E.g.: CNY:BTC -> BTC:BTS = CNY:BTS
            I.e.: BTS: interasset -> interasset: targetasset
        """
        for interasset in self.config.get("intermediate_assets", []):
            if interasset == base_symbol:
                continue
            if interasset not in self.data[base_symbol]:
                continue
            for ratio in self.data[base_symbol][interasset]:
                if interasset in self.data and target_symbol in self.data[interasset]:
                    for idx in range(0, len(self.data[interasset][target_symbol])):
                        if self.data[interasset][target_symbol][idx]["volume"] == 0:
                            continue
                        self.addPrice(
                            base_symbol,
                            target_symbol,
                            float(self.data[interasset][target_symbol][idx]["price"] * ratio["price"]),
                            float(self.data[interasset][target_symbol][idx]["volume"]),
                            sources=[
                                ratio["sources"],
                                self.data[interasset][target_symbol][idx]["sources"]
                            ]
                        )

    def derive3Markets(self, base_symbol, target_symbol):
        """ derive BTS prices for all assets in assets_derive
            This loop adds prices going via 3 markets:
            E.g.: GOLD:USD -> USD:BTC -> BTC:BTS = GOLD:BTS
            I.e.: BTS: interassetA -> interassetA: interassetB -> symbol: interassetB
        """
        if "intermediate_assets" not in self.config or not self.config["intermediate_assets"]:
            return

        if self.assetconf(base_symbol, "derive_across_3markets"):
            for interassetA in self.config["intermediate_assets"]:
                for interassetB in self.config["intermediate_assets"]:
                    if interassetB == base_symbol or interassetA == base_symbol or interassetA == interassetB:
                        continue
                    if interassetA not in self.data[interassetB] or interassetB not in self.data[base_symbol]:
                        continue

                    for ratioA in self.data[interassetB][interassetA]:
                        for ratioB in self.data[base_symbol][interassetB]:
                            if (
                                interassetA not in self.data or
                                target_symbol not in self.data[interassetA]
                            ):
                                continue
                            for idx in range(0, len(self.data[interassetA][target_symbol])):
                                if self.data[interassetA][target_symbol][idx]["volume"] == 0:
                                    continue
                                log.info("derive_across_3markets - found %s -> %s -> %s -> %s", base_symbol, interassetB, interassetA, target_symbol)
                                self.addPrice(
                                    base_symbol,
                                    target_symbol,
                                    float(self.data[interassetA][target_symbol][idx]["price"] * ratioA["price"] * ratioB["price"]),
                                    float(self.data[interassetA][target_symbol][idx]["volume"]),
                                    sources=[
                                        ratioB["sources"],
                                        ratioA["sources"],
                                        self.data[interassetA][target_symbol][idx]["sources"]
                                    ]
                                )

    def get_premium_details(self, smartcoin_symbol, realcoin_symbol, dex_price):
        details = {
            "dex_price": dex_price
        }

        if smartcoin_symbol in self.data:
            self.derive2Markets(smartcoin_symbol, realcoin_symbol)
            if realcoin_symbol in self.data[smartcoin_symbol]:
                details['alternative'] = self.data[smartcoin_symbol][realcoin_symbol]
        
        return details

    def load_previous_pid_data(self, historic_file):
        if historic_file and not os.path.exists(historic_file):
            return None

        with open(historic_file) as f:
            return json.load(f)

    def save_pid_data(self, historic_file, premium, i):
        with open(historic_file, 'w') as outfile:
            json.dump({'premium': premium, 'i': i}, outfile)
    
    # Cf BSIP-42: https://github.com/bitshares/bsips/blob/master/bsip-0042.md
    def compute_target_price(self, symbol, backing_symbol, real_price):
        
        ticker = Market("%s:%s" % (backing_symbol, symbol)).ticker()
        dex_price = float(ticker["latest"])
        settlement_price = float(ticker['baseSettlement_price'])
        premium = (real_price / dex_price) - 1
        details = self.get_premium_details('BIT{}'.format(symbol), symbol, dex_price)

        target_price_algorithm = self.assetconf(symbol, "target_price_algorithm", no_fail=True)
        
        adjusted_price = real_price
        if target_price_algorithm == 'adjusted_feed_price':
            # Kudos to Abit: https://bitsharestalk.org/index.php?topic=26315.msg322091#msg322091
            adjustment_scale = self.assetconf(symbol, "target_price_adjustment_scale")
            adjusted_price = settlement_price * (1 + premium * adjustment_scale)
        elif target_price_algorithm == 'adjusted_real_price_empowered':
            # Kudos to Abit: https://bitsharestalk.org/index.php?topic=26315.msg321699#msg321699
            # Kudos to gghi: https://bitsharestalk.org/index.php?topic=26839.msg321863#msg321863
            theorical_premium = self.assetconf(symbol, "target_price_theorical_premium")
            acceleration_factor = self.assetconf(symbol, "target_price_acceleration_factor")
            adjusted_price = real_price * pow(1 + premium + theorical_premium, acceleration_factor)
        elif target_price_algorithm == 'adjusted_dex_price_using_buckets':
            # Kudos to GDEX/Bitcrab: https://bitsharestalk.org/index.php?topic=26315.msg321931#msg321931
            if premium > 0:
                if premium <= 0.01:
                    adjusted_price = dex_price * (1 + (0.096 * (premium * 100))) 
                elif premium <= 0.024:
                    adjusted_price = dex_price * 1.096
                else:
                    adjusted_price = dex_price * (1 + (4 * premium)) 
        elif target_price_algorithm == 'pid':
            # Kudos to GDEX/Bitcrab: https://bitsharestalk.org/index.php?topic=26278.msg322246#msg322246
            proportional_factor = self.assetconf(symbol, "target_price_pid_proportional_factor")
            integral_factor = self.assetconf(symbol, "target_price_pid_integral_factor")
            derivative_factor = self.assetconf(symbol, "target_price_pid_derivative_factor")
            safe_upward_feed_change = self.assetconf(symbol, "target_price_pid_safe_upward_feed_change")
            safe_downward_feed_change = self.assetconf(symbol, "target_price_pid_safe_downward_feed_change")

            integral_adjustment_max = self.assetconf(symbol, "target_price_pid_integral_adjustment_max", no_fail=True)
            integral_adjustment_min = self.assetconf(symbol, "target_price_pid_integral_adjustment_min", no_fail=True)

            historic_file = self.assetconf(symbol, "target_price_pid_historic_value_file")
            previous_data = self.load_previous_pid_data(historic_file)

            p = proportional_factor * premium
            if previous_data:
                i = previous_data['i'] + (premium / integral_factor)
                d = derivative_factor * (premium - previous_data['premium'])
            else:
                # Initial values aim for adjusted_price = real_price when premium = 0.
                i = settlement_price / real_price - 1 - p
                d = 0

            # Optionaly sets limits to i.
            if integral_adjustment_max and i > integral_adjustment_max:
                i = integral_adjustment_max
            if integral_adjustment_min and i < integral_adjustment_min:
                i = integral_adjustment_min

            pid_adjustment = 1 + p + i + d
            if pid_adjustment > 1:
               safe_max_adjustment = 1.5 # Do not adjust dex price with more than 50%.
               safe_feed_adjustment =  safe_upward_feed_change * settlement_price / real_price # To avoid price jumps.
               adjustement = min(pid_adjustment, safe_max_adjustment, safe_feed_adjustment)
               adjusted_price = dex_price * adjustement 
            else:
               safe_feed_adjustment =  safe_downward_feed_change * settlement_price / real_price # To avoid price jumps.
               adjustment = max(pid_adjustment, safe_feed_adjustment)
               adjusted_price = dex_price * adjustment
            

            print('{} PID info: adjustment={}, pid={} (p={}, i={}, d={}), safe={}'.format(symbol, adjustement, pid_adjustment, p, i, d, safe_feed_adjustment))
            self.save_pid_data(historic_file, premium, i)


        return (premium, adjusted_price, details)



    def derive_asset(self, symbol):
        """ Derive prices for an asset by adding data from the
            exchanges to the internal state and processing through markets
        """
        asset = Asset(symbol, full=True)
        if not asset.is_bitasset:
            return
        short_backing_asset = Asset(asset["bitasset_data"]["options"]["short_backing_asset"])
        backing_symbol = short_backing_asset["symbol"]
        asset["short_backing_asset"] = short_backing_asset

        # Reset self.data
        self.reset()

        # Fill in self.data
        self.appendOriginalPrices(symbol)
        log.info("Computed data (raw): \n{}".format(self.data))
        self.derive2Markets(symbol, backing_symbol)
        self.derive3Markets(symbol, backing_symbol)
        log.info("Computed data (after derivation): \n{}".format(self.data))

        if symbol not in self.data:
            log.warn("'{}' not in self.data".format(symbol))
            return
        if backing_symbol not in self.data[symbol]:
            log.warn("'backing_symbol' ({}) not in self.data[{}]".format(backing_symbol, symbol))
            return
        assetvolume = [v["volume"] for v in self.data[symbol][backing_symbol]]
        assetprice = [p["price"] for p in self.data[symbol][backing_symbol]]

        if len(assetvolume) > 1:
            price_median = statistics.median([x["price"] for x in self.data[symbol][backing_symbol]])
            price_mean = statistics.mean([x["price"] for x in self.data[symbol][backing_symbol]])
            price_weighted = num.average(assetprice, weights=assetvolume)
            price_std = weighted_std(assetprice, assetvolume)
        elif len(assetvolume) == 1:
            price_median = assetprice[0]
            price_mean = assetprice[0]
            price_weighted = assetprice[0]
            price_std = 0
        else:
            print("[Warning] No market route found for %s. Skipping price" % symbol)
            return

        metric = self.assetconf(symbol, "metric")
        if metric == "median":
            p = price_median
        elif metric == "mean":
            p = price_mean
        elif metric == "weighted":
            p = price_weighted
        else:
            raise ValueError("Asset %s has an unknown metric '%s'" % (
                symbol,
                metric
            ))

        (premium, target_price, details) = self.compute_target_price(symbol, backing_symbol, p)

        cer = self.get_cer(symbol, target_price)

        # price conversion to "price for one symbol" i.e.  base=*, quote=symbol
        self.price_result[symbol] = {
            "price": target_price,
            "unadjusted_price": p,
            "cer": cer,
            "mean": price_mean,
            "median": price_median,
            "weighted": price_weighted,
            "std": price_std * 100,  # percentage
            "number": len(assetprice),
            "premium": premium * 100, # percentage
            "short_backing_symbol": backing_symbol,
            "mssr": self.assetconf(symbol, "maximum_short_squeeze_ratio"),
            "mcr": self.assetconf(symbol, "maintenance_collateral_ratio"),
            "log": self.data,
            "premium_details": details
        }

    def derive(self, assets_derive=set()):
        """ calculate self.feed prices in BTS for all assets given the exchange prices in USD,CNY,BTC,...
        """
        # Manage default assets to publish
        assets_derive = set(assets_derive)
        if not assets_derive:
            assets_derive = set(self.config["assets"])

        # create returning dictionary
        self.price_result = {}
        for symbol in assets_derive:
            self.price_result[symbol] = {}

        for symbol in assets_derive:
            self.derive_asset(symbol)

        # tests
        for symbol in assets_derive:
            if not self.price_result.get(symbol):
                continue
            self.obtain_price_change(symbol)
            self.obtain_flags(symbol)

        return self.price_result

    def get_prices(self):
        return self.price_result
