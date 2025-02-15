###############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
###############################################################################

from financepy.models.volatility_fns import VolFuncTypes
from financepy.utils.date import Date
from financepy.market.volatility.fx_vol_surface import FinFXDeltaMethod
from financepy.market.volatility.fx_vol_surface import FinFXATMMethod
from financepy.market.volatility.fx_vol_surface import FXVolSurface
from financepy.market.curves.discount_curve_flat import DiscountCurveFlat


verboseCalibration = False


def test_FinFXMktVolSurface1(capsys):
    # Example from Book extract by Iain Clarke using Tables 3.3 and 3.4
    # print("EURUSD EXAMPLE CLARK")

    value_dt = Date(10, 4, 2020)

    forName = "EUR"
    domName = "USD"
    forCCRate = 0.03460  # EUR
    domCCRate = 0.02940  # USD

    dom_discount_curve = DiscountCurveFlat(value_dt, domCCRate)
    for_discount_curve = DiscountCurveFlat(value_dt, forCCRate)

    currency_pair = forName + domName
    spot_fx_rate = 1.3465

    tenors = ['1M', '2M', '3M', '6M', '1Y', '2Y']
    atm_vols = [21.00, 21.00, 20.750, 19.400, 18.250, 17.677]
    marketStrangle25DeltaVols = [0.65, 0.75, 0.85, 0.90, 0.95, 0.85]
    riskReversal25DeltaVols = [-0.20, -0.25, -0.30, -0.50, -0.60, -0.562]

    notional_currency = forName

    atmMethod = FinFXATMMethod.FWD_DELTA_NEUTRAL
    delta_method = FinFXDeltaMethod.SPOT_DELTA
    vol_functionType = VolFuncTypes.CLARK

    fxMarket = FXVolSurface(value_dt,
                            spot_fx_rate,
                            currency_pair,
                            notional_currency,
                            dom_discount_curve,
                            for_discount_curve,
                            tenors,
                            atm_vols,
                            marketStrangle25DeltaVols,
                            riskReversal25DeltaVols,
                            atmMethod,
                            delta_method,
                            vol_functionType)

    fxMarket.check_calibration(verboseCalibration, tol=1e-5)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_FinFXMktVolSurface2(capsys):
    # Example from Book extract by Iain Clark using Tables 3.3 and 3.4
    # print("EURJPY EXAMPLE CLARK")

    value_dt = Date(10, 4, 2020)

    forName = "EUR"
    domName = "JPY"
    forCCRate = 0.0294  # EUR
    domCCRate = 0.0171  # USD

    dom_discount_curve = DiscountCurveFlat(value_dt, domCCRate)
    for_discount_curve = DiscountCurveFlat(value_dt, forCCRate)

    currency_pair = forName + domName
    spot_fx_rate = 90.72

    tenors = ['1M', '2M', '3M', '6M', '1Y', '2Y']
    atm_vols = [21.50, 20.50, 19.85, 18.00, 15.95, 14.009]
    marketStrangle25DeltaVols = [0.35, 0.325, 0.300, 0.225, 0.175, 0.100]
    riskReversal25DeltaVols = [-8.350, -8.650, -8.950, -9.250, -9.550, -9.500]

    notional_currency = forName

    atmMethod = FinFXATMMethod.FWD_DELTA_NEUTRAL_PREM_ADJ
    delta_method = FinFXDeltaMethod.SPOT_DELTA_PREM_ADJ

    fxMarket = FXVolSurface(value_dt,
                            spot_fx_rate,
                            currency_pair,
                            notional_currency,
                            dom_discount_curve,
                            for_discount_curve,
                            tenors,
                            atm_vols,
                            marketStrangle25DeltaVols,
                            riskReversal25DeltaVols,
                            atmMethod,
                            delta_method)

    fxMarket.check_calibration(verboseCalibration, tol=0.0005)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_FinFXMktVolSurface3(capsys):
    # EURUSD Example from Paper by Uwe Wystup using Tables 4
    #        print("EURUSD EXAMPLE WYSTUP")

    value_dt = Date(20, 1, 2009)

    forName = "EUR"
    domName = "USD"
    forCCRate = 0.020113  # EUR
    domCCRate = 0.003525  # USD

    dom_discount_curve = DiscountCurveFlat(value_dt, domCCRate)
    for_discount_curve = DiscountCurveFlat(value_dt, forCCRate)

    currency_pair = forName + domName
    spot_fx_rate = 1.3088

    tenors = ['1M']
    atm_vols = [21.6215]
    marketStrangle25DeltaVols = [0.7375]
    riskReversal25DeltaVols = [-0.50]

    notional_currency = forName

    atmMethod = FinFXATMMethod.FWD_DELTA_NEUTRAL
    delta_method = FinFXDeltaMethod.SPOT_DELTA

    fxMarket = FXVolSurface(value_dt,
                            spot_fx_rate,
                            currency_pair,
                            notional_currency,
                            dom_discount_curve,
                            for_discount_curve,
                            tenors,
                            atm_vols,
                            marketStrangle25DeltaVols,
                            riskReversal25DeltaVols,
                            atmMethod,
                            delta_method)

    fxMarket.check_calibration(verboseCalibration)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_FinFXMktVolSurface4(capsys):
    # USDJPY Example from Paper by Uwe Wystup using Tables 4

    value_dt = Date(20, 1, 2009)

    forName = "USD"
    domName = "JPY"
    forCCRate = 0.003525  # USD
    domCCRate = 0.0042875  # JPY

    dom_discount_curve = DiscountCurveFlat(value_dt, domCCRate)
    for_discount_curve = DiscountCurveFlat(value_dt, forCCRate)

    currency_pair = forName + domName
    spot_fx_rate = 90.68

    tenors = ['1M']
    atm_vols = [21.00]
    marketStrangle25DeltaVols = [0.184]
    riskReversal25DeltaVols = [-5.30]

    notional_currency = forName

    atmMethod = FinFXATMMethod.FWD_DELTA_NEUTRAL
    delta_method = FinFXDeltaMethod.SPOT_DELTA_PREM_ADJ

    fxMarket = FXVolSurface(value_dt,
                            spot_fx_rate,
                            currency_pair,
                            notional_currency,
                            dom_discount_curve,
                            for_discount_curve,
                            tenors,
                            atm_vols,
                            marketStrangle25DeltaVols,
                            riskReversal25DeltaVols,
                            atmMethod,
                            delta_method)

    fxMarket.check_calibration(verboseCalibration)
    captured = capsys.readouterr()
    assert captured.out == ""
