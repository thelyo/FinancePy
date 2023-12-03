###############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
###############################################################################

from financepy.market.curves.discount_curve_flat import DiscountCurveFlat
from financepy.utils.global_types import FinLongShort
from financepy.utils.date import Date
from financepy.products.equity.equity_forward import EquityForward


def test_equity_forward():

    value_dt = Date(13, 2, 2018)
    expiry_date = value_dt.add_months(12)

    stock_price = 130.0
    forward_price = 125.0  # Locked
    discount_rate = 0.05
    dividend_rate = 0.02

    expiry_date = value_dt.add_months(12)
    notional = 100.0

    discount_curve = DiscountCurveFlat(value_dt, discount_rate)
    dividend_curve = DiscountCurveFlat(value_dt, dividend_rate)

    equityForward = EquityForward(expiry_date,
                                  forward_price,
                                  notional,
                                  FinLongShort.LONG)

    fwdPrice = equityForward.forward(value_dt,
                                     stock_price,
                                     discount_curve,
                                     dividend_curve)

    fwdValue = equityForward.value(value_dt,
                                   stock_price,
                                   discount_curve,
                                   dividend_curve)

    assert round(fwdPrice, 4) == 133.9591
    assert round(fwdValue, 4) == 852.2149
