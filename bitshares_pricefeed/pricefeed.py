import statistics
import numpy as num
import psycopg2
import time
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
from dateutil.parser import parse
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
    price = {}
    volume = {}
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

    def derive2Markets(self, asset, target_symbol):
        """ derive BTS prices for all assets in assets_derive
            This loop adds prices going via 2 markets:
            E.g.: CNY:BTC -> BTC:BTS = CNY:BTS
            I.e.: BTS: interasset -> interasset: targetasset
        """
        symbol = asset["symbol"]

        for interasset in self.config.get("intermediate_assets", []):
            if interasset == symbol:
                continue
            if interasset not in self.data[symbol]:
                continue
            for ratio in self.data[symbol][interasset]:
                if interasset in self.data and target_symbol in self.data[interasset]:
                    for idx in range(0, len(self.data[interasset][target_symbol])):
                        if self.data[interasset][target_symbol][idx]["volume"] == 0:
                            continue
                        self.addPrice(
                            symbol,
                            target_symbol,
                            float(self.data[interasset][target_symbol][idx]["price"] * ratio["price"]),
                            float(self.data[interasset][target_symbol][idx]["volume"]),
                            sources=[
                                ratio["sources"],
                                self.data[interasset][target_symbol][idx]["sources"]
                            ]
                        )

    def derive3Markets(self, asset, target_symbol):
        """ derive BTS prices for all assets in assets_derive
            This loop adds prices going via 3 markets:
            E.g.: GOLD:USD -> USD:BTC -> BTC:BTS = GOLD:BTS
            I.e.: BTS: interassetA -> interassetA: interassetB -> symbol: interassetB
        """
        symbol = asset["symbol"]

        if "intermediate_assets" not in self.config or not self.config["intermediate_assets"]:
            return

        if self.assetconf(symbol, "derive_across_3markets"):
            for interassetA in self.config["intermediate_assets"]:
                for interassetB in self.config["intermediate_assets"]:
                    if interassetB == symbol or interassetA == symbol or interassetA == interassetB:
                        continue
                    if interassetA not in self.data[interassetB] or interassetB not in self.data[symbol]:
                        continue

                    for ratioA in self.data[interassetB][interassetA]:
                        for ratioB in self.data[symbol][interassetB]:
                            if (
                                interassetA not in self.data or
                                target_symbol not in self.data[interassetA]
                            ):
                                continue
                            for idx in range(0, len(self.data[interassetA][target_symbol])):
                                if self.data[interassetA][target_symbol][idx]["volume"] == 0:
                                    continue
                                log.info("derive_across_3markets - found %s -> %s -> %s -> %s", symbol, interassetB, interassetA, target_symbol)
                                self.addPrice(
                                    symbol,
                                    target_symbol,
                                    float(self.data[interassetA][target_symbol][idx]["price"] * ratioA["price"] * ratioB["price"]),
                                    float(self.data[interassetA][target_symbol][idx]["volume"]),
                                    sources=[
                                        ratioB["sources"],
                                        ratioA["sources"],
                                        self.data[interassetA][target_symbol][idx]["sources"]
                                    ]
                                )
    
    # Cf BSIP-42: https://github.com/bitshares/bsips/blob/master/bsip-0042.md
    def compute_target_price(self, symbol, backing_symbol, real_price):
        ticker = Market("%s:%s" % (backing_symbol, symbol)).ticker()
        dex_price = float(ticker["latest"])
        settlement_price = float(ticker['baseSettlement_price'])
        premium = (real_price / dex_price) - 1

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
            # Kudos to GDEX: https://bitsharestalk.org/index.php?topic=26315.msg321931#msg321931
            if premium > 0:
                if premium <= 0.01:
                    adjusted_price = dex_price * (1 + (0.096 * (premium * 100))) 
                elif premium <= 0.024:
                    adjusted_price = dex_price * 1.096
                else:
                    adjusted_price = dex_price * (1 + (4 * premium)) 
        elif target_price_algorithm=="gugu":
            print("\033[1;31;40mmagicwallet for CNY\033[0m") 
            print("\033[1;31;40充提手续费率%s\033[0m" % self.feed["magicwallet"]["CNY"]["BITCNY"]["price"])
            print("\033[1;31;40当前价格%s\033[0m" % str(1/float(self.feed["bitshares"]["BTS"]["CNY"]["price"])))
            print("计算C")
            market = Market("BTS:CNY")
            c=market.ticker()['baseSettlement_price']/market.ticker()['latest']
            print("\033[1;31; 当前C%s\033[0m" %  str(c))
            print("获取数据库数据")
            conn = psycopg2.connect(database=self.config["database"]["dbname"], user=self.config["database"]["dbuser"], password=self.config["database"]["dbpwd"], host=self.config["database"]["dbhost"], port=self.config["database"]["dbport"])
            CNY=1/float(self.feed["bitshares"]["BTS"]["CNY"]["price"])
            mrate=float(self.feed["magicwallet"]["CNY"]["BITCNY"]["price"])
            mrate_old=0
            crate=1
            cur_mrate = conn.cursor()
            cur_mrate.execute("SELECT value from magicwalletrate order by createdate desc limit 1")
            rows_mrate=cur_mrate.fetchall()
            if rows_mrate==[]:
                cur_mrate.execute("INSERT INTO magicwalletrate(id,value) VALUES(1,'"+str(mrate)+"')")
                conn.commit()
            else:
                for row in rows_mrate:
                    mrate_old=float(row[0])
                cur_mrate.execute("UPDATE magicwalletrate set value='"+str(mrate)+"' where id=1")
                conn.commit()
            
            upline=0
            lowline=0
            cur2=conn.cursor()
            cur2.execute("SELECT id, name, value from params")
            prows = cur2.fetchall()
            for row in prows:
                if row[1]=='upline':
                    upline=row[2]
                elif row[1]=='lowline':
                    lowline=row[2]
            if mrate_old==0:
                crate=1
            elif 0.99<mrate<1.01:
                crate=1
            elif mrate>mrate_old:
                if mrate>1:
                    crate=1+upline
                else:
                    crate=1-lowline
            else:
                if mrate>1:
                    crate=1+lowline
                else:
                    crate=1-upline
            print("\033[1;31;当前Crate%s\033[0m" %  crate)

            cdatetime=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            cur=conn.cursor()
            cur.execute("SELECT id, cvalue,mrate ,createdate from record order by createdate desc limit 2")
            rows = cur.fetchall()
            if rows==[]:
                c=c*crate
            else :
                c=float(rows[0][1])
                c=c*crate
                cdatetime=rows[0][3].strftime('%Y-%m-%d %H:%M:%S') 
            
            if c > self.config["flaghigh"]:
                c=self.config["flaghigh"]
            elif c<self.config["flaglow"]:
                c=self.config["flaglow"]
            print("\033[1;31;最终C%s\033[0m" %  str(c))

            CNY=CNY*c
            print("\033[1;31;最终CNY喂价%s\033[0m" %  str(CNY))
            sqlinsert="INSERT INTO record (btsprice, feedprice, cvalue,mrate,myfeedprice) \
            VALUES ('"+str(market.ticker()['latest'])+"','"+str(market.ticker()['baseSettlement_price'])+"','"+str(market.ticker()['baseSettlement_price']/market.ticker()['latest'])+"','"+str(mrate)+"','"+str(CNY)+"')"
            print('timedis')
            print((parse(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()))- parse(cdatetime)).total_seconds()/(60*60))
            if self.config["changehour"]<((parse(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()))- parse(cdatetime)).total_seconds()/(60*60)):
                cur.execute(sqlinsert)
                conn.commit()
            elif rows==[]:
                cur.execute(sqlinsert)
                conn.commit()

            conn.close()
            print('OK')
            adjusted_price=CNY
        return (premium, adjusted_price)



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
        self.derive2Markets(asset, backing_symbol)
        self.derive3Markets(asset, backing_symbol)
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

        (premium, target_price) = self.compute_target_price(symbol, backing_symbol, p)

        cer = self.get_cer(symbol, p)

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
            "log": self.data
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
