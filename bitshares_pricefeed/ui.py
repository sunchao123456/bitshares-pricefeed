import os
import click
import logging
import yaml
from math import fabs
from datetime import datetime, timezone
from bitshares.price import Price
from bitshares.asset import Asset
from prettytable import PrettyTable
from functools import update_wrapper
from bitshares import BitShares
from bitshares.instance import set_shared_bitshares_instance
log = logging.getLogger(__name__)


def configfile(f):
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        ctx.config = yaml.load(open(ctx.obj["configfile"]))
        return ctx.invoke(f, *args, **kwargs)
    return update_wrapper(new_func, f)


def priceChange(new, old):
    if float(old) == 0.0:
        return -1
    else:
        percent = ((float(new) - float(old))) / float(old) * 100
        if percent >= 0:
            return click.style("%.2f" % percent, fg="green")
        else:
            return click.style("%.2f" % percent, fg="red")


def highlightLargeDeviation(value, ref, thres=5):
    percent = ((float(value) - float(ref))) / float(ref) * 100
    if fabs(percent) >= thres:
        return click.style("%+5.2f" % percent, fg="red")
    else:
        return click.style("%+5.2f" % percent, fg="green")


def formatPrice(f):
    return click.style("%.6f" % f, fg="yellow")


def formatStd(f):
    return click.style("%.2f" % f, bold=True)


def print_log(feeds):
    t = PrettyTable([
        "base",
        "quote",
        "price",
        "diff",
        "quote volume",
        "source"
    ])
    t.align = 'l'
    for symbol, feed in feeds.items():
        asset = Asset(symbol, full=True)
        asset.ensure_full()
        short_backing_asset = Asset(
            asset["bitasset_data"]["options"]["short_backing_asset"])
        backing_symbol = short_backing_asset["symbol"]
        data = feed.get("log", {})
        price = data.get(symbol)
        if not price:
            continue
        for d in price.get(backing_symbol, []):
            t.add_row([
                symbol,
                backing_symbol,
                formatPrice(d.get("price")),
                highlightLargeDeviation(d.get("price"), feed["price"]),
                d.get("volume"),
                str(d.get("sources")),
            ])
    print(t.get_string())

def print_premium_details(feeds):
    for symbol, feed in feeds.items():
        if not feed:
            continue
        print('Premium details for {}:'.format(symbol))
        print('  BIT{}/BTS (on DEX): {} ({})'.
            format(symbol, formatPrice(feed['premium_details']['dex_price']), \
                   priceChange(feed['premium_details']['dex_price'], feed["unadjusted_price"])))
        if 'alternative' in feed['premium_details']:
            print('  BIT{}/{} (alternative premiums):'.format(symbol, symbol))
            for alt in feed['premium_details']['alternative']:
                print('    - {} : {} ({})'.format(alt['sources'], formatPrice(alt['price']), priceChange(alt['price'], 1)))

def print_prices(feeds):
    t = PrettyTable([
        "symbol", "collateral",
        "new price", "cer", "premium", "unadjusted price",
        "mean", "median", "wgt. avg.",
        "wgt. std (#)", "blockchain",
        "mssr", "mcr",
        "my last price", "last update",
    ])
    t.align = 'c'
    t.border = True

    for symbol, feed in feeds.items():
        if not feed:
            continue
        collateral = feed["short_backing_symbol"]
        myprice = feed["price"]
        blockchain = feed["global_feed"]["settlement_price"].as_quote(collateral)['price']
        if "current_feed" in feed and feed["current_feed"]:
            last = feed["current_feed"]["settlement_price"].as_quote(collateral)['price']
            age = (str(datetime.now(timezone.utc) - feed["current_feed"]["date"]))
        else:
            last = -1.0
            age = "unknown"
        # Get Final Price according to price metric
        t.add_row([
            symbol,
            ("%s" % collateral),
            ("%s" % formatPrice(feed["price"])),
            ("%s" % formatPrice(feed["cer"])),
            ("%.1f%%" % feed["premium"]),
            ("%s (%s)" % (formatPrice(feed["unadjusted_price"]), priceChange(myprice, feed.get("unadjusted_price")))),
            ("%s (%s)" % (formatPrice(feed["mean"]), priceChange(myprice, feed.get("mean")))),
            ("%s (%s)" % (formatPrice(feed["median"]), priceChange(myprice, feed.get("median")))),
            ("%s (%s)" % (formatPrice(feed["weighted"]), priceChange(myprice, feed.get("weighted")))),
            ("%s (%2d)" % (formatStd(feed["std"]), feed.get("number"))),
            ("%s (%s)" % (formatPrice(blockchain), priceChange(myprice, blockchain))),
            ("%.1f%%" % feed["mssr"]),
            ("%.1f%%" % feed["mcr"]),
            ("%s (%s)" % (formatPrice(last), priceChange(myprice, last))),
            age + " ago"
        ])
    print(t.get_string())


def warning(msg):
    click.echo(
        "[" +
        click.style("Warning", fg="yellow") +
        "] " + msg,
        err=True  # this will cause click to post to stderr
    )


def confirmwarning(msg):
    return click.confirm(
        "[" +
        click.style("Warning", fg="yellow") +
        "] " + msg
    )


def alert(msg):
    click.echo(
        "[" +
        click.style("alert", fg="yellow") +
        "] " + msg,
        err=True  # this will cause click to post to stderr
    )


def confirmalert(msg):
    return click.confirm(
        "[" +
        click.style("Alert", fg="red") +
        "] " + msg
    )
