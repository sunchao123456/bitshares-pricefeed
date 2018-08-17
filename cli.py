#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")

from bitshares_pricefeed import cli

cli.main()
