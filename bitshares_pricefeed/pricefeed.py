import statistics
import numpy as num
import psycopg2
import time
import json
import os.path
from math import fabs, sqrt
from bitshares import BitShares
from bitshares.instance import shared_bitshares_instance
from bitshares.account import Account
from bitshares.asset import Asset
from bitshares.price import Price
from bitshares.amount import Amount
from bitshares.market import Market
from bitshares.witness import Witness
from bitshares.exceptions import AccountDoesNotExistsException
from datetime import datetime, date, timezone, timedelta
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

    def get_cer(self, symbol, price, asset):
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
            cer = price.as_quote(orientation["quote"]["symbol"])
        else:
            cer = price * self.assetconf(symbol, "core_exchange_factor")
        
        is_global_settled = bool(int(asset['bitasset_data']['settlement_fund']) != 0)
        if is_global_settled:
            global_settlement_price = Price(asset['bitasset_data']['settlement_price'])
            print('WARN: {} is globally settled, check cer ({}) > global_settlement_price ({}).'.format(symbol, cer, global_settlement_price))
            if cer < global_settlement_price:
                print('WARN: Overwrite CER for {} to global_settlement_price'.format(symbol))
                cer = global_settlement_price.as_base(symbol)

        return float(cer)

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
        elif target_price_algorithm=="gugublack":
            print("\033[1;31;40GUGUBLACK for CNY\033[0m") 
            CNY=1/float(self.feed["bitshares"]["BTS"]["CNY"]["price"])
            print("\033[1;31;40mCNY喂价%s\033[0m" %  str(CNY))
            bitshares = BitShares()
            asset=Asset("CNY", bitshares_instance=bitshares)
            call_orders = asset.get_call_orders(limit=10)
            minprice=float(call_orders[0]['collateral']/call_orders[0]['debt'])
            saveprice=minprice*1.11
            print("\033[1;31;40m黑天鹅价格%s\033[0m" %  str(minprice))
            print("\033[1;31;40m黑天鹅价格1.11倍%s\033[0m" %  str(saveprice))
            if CNY<minprice :
                CNY=saveprice
            print("\033[1;31;40m最终CNY喂价%s\033[0m" %  str(CNY))
            print('OK')
            adjusted_price=CNY
        elif target_price_algorithm=="gugu":
            print("\033[1;31;40mmagicwallet for CNY\033[0m") 
            print(self.feed["magicwallet"])
            if self.feed["magicwallet"]=={}:
                mrate=1
                print("\033[1;31;40m充提手续费率%s\033[0m" % "1")
            else:
                mrate=float(self.feed["magicwallet"]["CNY"]["BITCNY"]["price"])
                print("\033[1;31;40m充提手续费率%s\033[0m" % self.feed["magicwallet"]["CNY"]["BITCNY"]["price"])
            
            print("\033[1;31;40m当前价格%s\033[0m" % str(1/float(self.feed["bitshares"]["BTS"]["CNY"]["price"])))
            print("计算C")
            market = Market("BTS:CNY")
            c=market.ticker()['baseSettlement_price']/market.ticker()['latest']
            print("\033[1;31;40m 当前C%s\033[0m" %  str(c))
            print("获取数据库数据")
            conn = psycopg2.connect(database=self.config["database"]["dbname"], user=self.config["database"]["dbuser"], password=self.config["database"]["dbpwd"], host=self.config["database"]["dbhost"], port=self.config["database"]["dbport"])
            CNY=1/float(self.feed["bitshares"]["BTS"]["CNY"]["price"])
            
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
            cdatetime=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            cur=conn.cursor()
            enddate=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()) 
            startdate = (datetime.now()+ timedelta(hours=-1)).strftime('%Y-%m-%d %H:%M:%S')    
            where=" where createdate>'"+startdate+"' and createdate<'"+enddate+"'"
            sql="SELECT max(cvalue) from record "+where
            if mrate<1:
                sql="SELECT min(cvalue) from record "+where
            else:
                sql="SELECT max(cvalue) from record "+where

            if mrate_old==0:
                crate=1
            elif 0.99<mrate<=1.005:
                print("\033[1;31;40mmid value\033[0m")
                sql="SELECT avg(cast (cvalue as numeric)) from record "+where
                crate=1
            elif 0.985<mrate<=0.99:
                if mrate<1:
                    crate=1-self.config["vblacne"]
                else:
                    crate=1+self.config["vblacne"]
            elif 1.005<mrate<1.01:
                if mrate<1:
                    crate=1-self.config["vblacne"]
                else:
                    crate=1+self.config["vblacne"]
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
            print("\033[1;31;40m当前Crate%s\033[0m" %  crate)
            print(sql)

            
            cur.execute(sql)
            rows = cur.fetchall()
            print(rows[0][0])
            if rows==[] or rows[0][0]==None:
                c=c*crate
            else :
                c=float(rows[0][0])
                c=c*crate
                #cdatetime=rows[0][3].strftime('%Y-%m-%d %H:%M:%S') 
            
            if c > self.config["flaghigh"]:
                c=self.config["flaghigh"]
            elif c<self.config["flaglow"]:
                c=self.config["flaglow"]
            print("\033[1;31;40m最终C%s\033[0m" %  str(c))

            CNY=CNY*c
            bitshares = BitShares()
            asset=Asset("CNY", bitshares_instance=bitshares)
            call_orders = asset.get_call_orders(limit=10)
            minprice=float(call_orders[0]['collateral']/call_orders[0]['debt'])
            saveprice=minprice*1.11
            print("\033[1;31;40m黑天鹅价格%s\033[0m" %  str(minprice))
            print("\033[1;31;40m黑天鹅价格1.11倍%s\033[0m" %  str(saveprice))
            if CNY<minprice :
                CNY=saveprice
            print("\033[1;31;40m最终CNY喂价%s\033[0m" %  str(CNY))
            sqlinsert="INSERT INTO record (btsprice, feedprice, cvalue,mrate,myfeedprice) \
            VALUES ('"+str(market.ticker()['latest'])+"','"+str(market.ticker()['baseSettlement_price'])+"','"+str(market.ticker()['baseSettlement_price']/market.ticker()['latest'])+"','"+str(mrate)+"','"+str(CNY)+"')"
            #print('timedis')
            #print((parse(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()))- parse(cdatetime)).total_seconds()/(60*60))
            #if self.config["changehour"]<((parse(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()))- parse(cdatetime)).total_seconds()/(60*60)):
            cur.execute(sqlinsert)
            conn.commit()

            conn.close()
            print('OK')
            adjusted_price=CNY
        elif target_price_algorithm=="guguusd":
            print("\033[1;32;40mmagicwallet for USD\033[0m")
            market1 = Market("BTS:USD")
            c=market1.ticker()['baseSettlement_price']/market1.ticker()['latest']
            print("\033[1;32;40m 当前C%s\033[0m" %  str(c))

            #get now rate
            market = Market("BTS:CNY")
            c2=float(str(market1.ticker()["latest"]).split(' ')[0])/float(str(market.ticker()["latest"]).split(' ')[0])
 
            print("\033[1;32;40m 当前bitsharesUSDrate%s\033[0m" %  str(c2)) 
            c_new=self.feed["sina"]["USD"]["CNY"]["price"]
            print("\033[1;32;40m 当前CNYUSDrate%s\033[0m" %  str(c_new))
            usdrate=c_new/c2
            print("\033[1;33;40m 当前C%s\033[0m" %  str(usdrate))
            print("\033[1;32;40m获取数据库数据\033[0m")
            conn = psycopg2.connect(database=self.config["database"]["dbname"], user=self.config["database"]["dbuser"], password=self.config["database"]["dbpwd"], host=self.config["database"]["dbhost"], port=self.config["database"]["dbport"])
            usdrate_old=0
            
            cur_mrate = conn.cursor()
            cur_mrate.execute("SELECT value from usdrate order by createdate desc limit 1")
            rows_mrate=cur_mrate.fetchall()
            if rows_mrate==[]:
                cur_mrate.execute("INSERT INTO usdrate(id,value) VALUES(1,'"+str(usdrate)+"')")
                conn.commit()
            else:
                for row in rows_mrate:
                    usdrate_old=float(row[0])
                cur_mrate.execute("UPDATE usdrate set value='"+str(usdrate)+"' where id=1")
                conn.commit()

            upline=0
            lowline=0
            cur2=conn.cursor()
            cur2.execute("SELECT id, name, value from params")
            prows = cur2.fetchall()
            for row in prows:
                if row[1]=='upline':
                    upline=float(row[2])
                elif row[1]=='lowline':
                    lowline=float(row[2])
            crate=1

            cdatetime=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            cur=conn.cursor()
            enddate=time.strftime('%Y-%m-%d %H:%M:%S',time.localtime()) 
            startdate = (datetime.now()+ timedelta(hours=-1)).strftime('%Y-%m-%d %H:%M:%S')    
            where=" where createdate>'"+startdate+"' and createdate<'"+enddate+"'"
            sql="SELECT max(cvalue) from recordusd "+where
            if usdrate<1:
                sql="SELECT min(cvalue) from recordusd "+where
            else:
                sql="SELECT max(cvalue) from recordusd "+where

            if usdrate_old==0:
                crate=1
            elif 0.99<usdrate<1.01:
                if usdrate<1:
                    crate=1-self.config["vblacne"]
                else:
                    crate=1+self.config["vblacne"]
            elif usdrate>usdrate_old: 
                if usdrate>1:
                    crate=1+upline
                else:
                    crate=1-lowline
            else: 
                if usdrate>1:
                    crate=1+lowline
                else:
                    crate=1-upline
            print("\033[1;31;40m当前Crate%s\033[0m" %  str(crate))
            print(sql)

            
            cur.execute(sql)
            rows = cur.fetchall()
            print(rows[0][0])
            if rows==[] or rows[0][0]==None:
                c=c*crate
            else :
                c=float(rows[0][0])
                c=c*crate
                #cdatetime=rows[0][3].strftime('%Y-%m-%d %H:%M:%S') 
            
            if c > self.config["flaghigh"]:
                c=self.config["flaghigh"]
            elif c<self.config["flaglow"]:
                c=self.config["flaglow"]
            print("\033[1;32;40m最终C%s\033[0m" %  str(c))
            



            
            USD=1/float(self.feed["bitshares"]["BTS"]["USD"]["price"])
            USD=USD*c
            print("\033[1;32;40m最终USD's feedprice%s\033[0m" % str(USD))
            sqlinsert="INSERT INTO recordusd (btsprice, feedprice, cvalue,mrate,myfeedprice) \
            VALUES ('"+str(market1.ticker()['latest'])+"','"+str(market1.ticker()['baseSettlement_price'])+"','"+str(market1.ticker()['baseSettlement_price']/market1.ticker()['latest'])+"','"+str(usdrate)+"','"+str(USD)+"')"
            
            cur.execute(sqlinsert)
            conn.commit()

            conn.close()
            print('OK')
            adjusted_price=USD
            


        return (premium, adjusted_price,details)



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

        cer = self.get_cer(symbol, target_price, asset)

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
