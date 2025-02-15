###############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
###############################################################################

import sys
sys.path.append("..")

from financepy.products.fx.fx_forward import FXForward
from financepy.utils.day_count import DayCountTypes
from financepy.utils.calendar import CalendarTypes
from financepy.products.rates.ibor_single_curve import IborSingleCurve
from financepy.products.rates.ibor_deposit import IborDeposit
from financepy.utils.date import Date
from FinTestCases import FinTestCases, globalTestCaseMode


test_cases = FinTestCases(__file__, globalTestCaseMode)

##########################################################################


def test_FinFXForward():

    #  https://stackoverflow.com/questions/48778712
    #  /fx-vanilla-call-price-in-quantlib-doesnt-match-bloomberg

    value_dt = Date(13, 2, 2018)
    expiry_dt = value_dt.add_months(12)
    # Forward is on EURUSD which is expressed as number of USD per EUR
    # ccy1 = EUR and ccy2 = USD
    forName = "EUR"
    domName = "USD"
    currency_pair = forName + domName  # Always ccy1ccy2
    spot_fx_rate = 1.300  # USD per EUR
    strike_fx_rate = 1.365  # USD per EUR
    ccy1InterestRate = 0.02  # USD Rates
    ccy2InterestRate = 0.05  # EUR rates

    ###########################################################################

    spot_days = 0
    settle_dt = value_dt.add_weekdays(spot_days)
    maturity_dt = settle_dt.add_months(12)
    notional = 100.0
    cal_type = CalendarTypes.TARGET

    depos = []
    fras = []
    swaps = []
    deposit_rate = ccy1InterestRate
    depo = IborDeposit(settle_dt, maturity_dt, deposit_rate,
                       DayCountTypes.ACT_360, notional, cal_type)
    depos.append(depo)
    for_discount_curve = IborSingleCurve(value_dt, depos, fras, swaps)

    depos = []
    fras = []
    swaps = []
    deposit_rate = ccy2InterestRate
    depo = IborDeposit(settle_dt, maturity_dt, deposit_rate,
                       DayCountTypes.ACT_360, notional, cal_type)
    depos.append(depo)
    dom_discount_curve = IborSingleCurve(value_dt, depos, fras, swaps)

    notional = 100.0
    notional_currency = forName

    fxForward = FXForward(expiry_dt,
                          strike_fx_rate,
                          currency_pair,
                          notional,
                          notional_currency)

    test_cases.header("SPOT FX", "FX FWD", "VALUE_BS")

    fwdValue = fxForward.value(value_dt, spot_fx_rate,
                               dom_discount_curve, for_discount_curve)

    fwdFXRate = fxForward.forward(value_dt, spot_fx_rate,
                                  dom_discount_curve,
                                  for_discount_curve)

    test_cases.print(spot_fx_rate, fwdFXRate, fwdValue)

###############################################################################


test_FinFXForward()
test_cases.compareTestCases()
