###############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
###############################################################################

import sys
sys.path.append("..")

from FinTestCases import FinTestCases, globalTestCaseMode
from financepy.products.bonds.bond import Bond
from financepy.products.bonds.bond import YTMCalcType

from financepy.products.bonds.zero_curve import BondZeroCurve

from financepy.utils.date import Date, from_datetime
from financepy.utils.day_count import DayCountTypes
from financepy.utils.frequency import FrequencyTypes
import datetime as dt
import os

test_cases = FinTestCases(__file__, globalTestCaseMode)

plotGraphs = False

###############################################################################


def test_BondZeroCurve():

    import pandas as pd
    path = os.path.join(os.path.dirname(__file__), './data/giltBondPrices.txt')
    bondDataFrame = pd.read_csv(path, sep='\t')
    bondDataFrame['mid'] = 0.5*(bondDataFrame['bid'] + bondDataFrame['ask'])

    freq_type = FrequencyTypes.SEMI_ANNUAL
    dc_type = DayCountTypes.ACT_ACT_ICMA
    settlement = Date(19, 9, 2012)

    bonds = []
    clean_prices = []

    for _, bondRow in bondDataFrame.iterrows():
        date_string = bondRow['maturity']
        mat_date_time = dt.datetime.strptime(date_string, '%d-%b-%y')
        maturity_dt = from_datetime(mat_date_time)
        issue_dt = Date(maturity_dt._d, maturity_dt._m, 2000)
        coupon = bondRow['coupon']/100.0
        clean_price = bondRow['mid']
        bond = Bond(issue_dt, maturity_dt, coupon, freq_type, dc_type)
        bonds.append(bond)
        clean_prices.append(clean_price)

###############################################################################

    bondCurve = BondZeroCurve(settlement, bonds, clean_prices)

    test_cases.header("DATE", "ZERO RATE")

    for _, bond in bondDataFrame.iterrows():

        date_string = bond['maturity']
        mat_date_time = dt.datetime.strptime(date_string, '%d-%b-%y')
        maturity_dt = from_datetime(mat_date_time)
        zero_rate = bondCurve.zero_rate(maturity_dt)
        test_cases.print(maturity_dt, zero_rate)

    if plotGraphs:
        bondCurve.plot("BOND CURVE")


###############################################################################

test_BondZeroCurve()
test_cases.compareTestCases()
