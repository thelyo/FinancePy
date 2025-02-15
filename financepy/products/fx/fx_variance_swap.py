##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################

import numpy as np

from ...utils.error import FinError
from ...utils.date import Date
from ...utils.math import ONE_MILLION
from ...utils.global_vars import gDaysInYear
from ...utils.global_types import OptionTypes
from .fx_vanilla_option import FXVanillaOption
from ...models.black_scholes import BlackScholes

from ...utils.helpers import check_argument_types

###############################################################################


class FinFXVarianceSwap:
    """ Class for managing an FX variance swap contract. """

    def __init__(self,
                 effective_dt: Date,
                 maturity_dt_or_tenor: [Date, str],
                 strike_variance: float,
                 notional: float = ONE_MILLION,
                 pay_strike_flag: bool = True):
        """ Create variance swap contract. """

        check_argument_types(self.__init__, locals())

        if type(maturity_dt_or_tenor) == Date:
            maturity_dt = maturity_dt_or_tenor
        else:
            maturity_dt = effective_dt.add_tenor(maturity_dt_or_tenor)

        if effective_dt >= maturity_dt:
            raise FinError("Start date after or same as maturity date")

        self._effective_dt = effective_dt
        self._maturity_dt = maturity_dt
        self._strike_variance = strike_variance
        self._notional = notional
        self._payStrike = pay_strike_flag

        # Replication portfolio is stored
        self._num_put_options = 0
        self._num_call_options = 0
        self._putWts = []
        self._put_strikes = []
        self._callWts = []
        self._call_strikes = []

###############################################################################

    def value(self,
              value_dt,
              realisedVar,
              fair_strikeVar,
              libor_curve):
        """ Calculate the value of the variance swap based on the realised
        volatility to the valuation date, the forward looking implied
        volatility to the maturity date using the libor discount curve. """

        if isinstance(value_dt, Date) is False:
            raise FinError("Valuation date is not a Date")

        if value_dt > self._expiry_dt:
            raise FinError("Valuation date after expiry date.")

        if libor_curve._value_dt != value_dt:
            raise FinError(
                "Domestic Curve valuation date not same as option value date")

        t1 = (value_dt - self._effective_dt) / gDaysInYear
        t2 = (self._maturity_dt - self._effective_dt) / gDaysInYear

        expectedVariance = t1 * realisedVar/t2
        expectedVariance += (t2-t1) * fair_strikeVar / t2

        payoff = expectedVariance - self._strike_variance

        df = libor_curve.df(self._maturity_dt)
        v = payoff * self._notional * df
        return v

###############################################################################

    def fair_strike_approx(self,
                           value_dt,
                           fwdStockPrice,
                           strikes,
                           volatilities):
        """ This is an approximation of the fair strike variance by Demeterfi
        et al. (1999) which assumes that sigma(K) = sigma(F) - b(K-F)/F where
        F is the forward stock price and sigma(F) is the ATM forward vol. """

        f = fwdStockPrice

        # TODO Linear interpolation - to be revisited
        atm_vol = np.interp(f, strikes, volatilities)
        t_mat = (self._maturity_dt - value_dt)/gDaysInYear

        """ Calculate the slope of the volatility curve by taking the end
        points in the volatilities and strikes to calculate the gradient."""

        dvol = volatilities[-1] - volatilities[0]
        dK = strikes[-1] - strikes[0]
        b = f * dvol / dK
        var = (atm_vol**2) * np.sqrt(1.0+3.0*t_mat*(b**2))
        return var

###############################################################################

    def fair_strike(self,
                    value_dt,
                    stock_price,
                    dividend_curve,
                    volatility_curve,
                    num_call_options,
                    num_put_options,
                    strike_spacing,
                    discount_curve,
                    use_forward=True):
        """ Calculate the implied variance according to the volatility surface
        using a static replication methodology with a specially weighted
        portfolio of put and call options across a range of strikes using the
        approximate method set out by Demeterfi et al. 1999. """

        self._num_put_options = num_put_options
        self._num_call_options = num_call_options

        call_type = OptionTypes.EUROPEAN_CALL
        put_type = OptionTypes.EUROPEAN_PUT

        t_mat = (self._maturity_dt - value_dt)/gDaysInYear

        df = discount_curve.df(t_mat)
        r = - np.log(df)/t_mat

        dq = dividend_curve.df(t_mat)
        q = - np.log(dq)/t_mat

        s0 = stock_price
        g = np.exp((r-q)*t_mat)
        fwd = stock_price * g

        # This fixes the centre strike of the replication options
        if use_forward is True:
            sstar = fwd
        else:
            sstar = stock_price

        """ Replication argument from Demeterfi, Derman, Kamal and Zhou from
        Goldman Sachs Research notes March 1999. See Appendix A. This aim is
        to use calls and puts to approximate the payoff of a log contract """

        minStrike = sstar - (num_put_options+1) * strike_spacing

        self._putWts = []
        self._put_strikes = []
        self._callWts = []
        self._call_strikes = []

        # if the lower strike is < 0 we go to as low as the strike spacing
        if minStrike < strike_spacing:
            k = sstar
            klist = [sstar]
            while k >= strike_spacing:
                k -= strike_spacing
                klist.append(k)
            putK = np.array(klist)
            self._num_put_options = len(putK) - 1
        else:
            putK = np.linspace(sstar, minStrike, num_put_options+2)

        self._put_strikes = putK

        maxStrike = sstar + (num_call_options+1) * strike_spacing
        callK = np.linspace(sstar, maxStrike, num_call_options+2)

        self._call_strikes = callK

        optionTotal = 2.0*(r*t_mat - (s0*g/sstar-1.0) - np.log(sstar/s0))/t_mat

        self._callWts = np.zeros(num_call_options)
        self._putWts = np.zeros(num_put_options)

        def f(x): return (2.0/t_mat)*((x-sstar)/sstar-np.log(x/sstar))

        sumWts = 0.0
        for n in range(0, self._num_put_options):
            kp = putK[n+1]
            k = putK[n]
            self._putWts[n] = (f(kp)-f(k))/(k-kp) - sumWts
            sumWts += self._putWts[n]

        sumWts = 0.0
        for n in range(0, self._num_call_options):
            kp = callK[n+1]
            k = callK[n]
            self._callWts[n] = (f(kp)-f(k))/(kp-k) - sumWts
            sumWts += self._callWts[n]

        piPut = 0.0
        for n in range(0, num_put_options):
            k = putK[n]
            vol = volatility_curve.volatility(k)
            opt = FXVanillaOption(self._maturity_dt, k, put_type)
            model = BlackScholes(vol)
            v = opt.value(value_dt, s0, discount_curve,
                          dividend_curve, model)
            piPut += v * self._putWts[n]

        piCall = 0.0
        for n in range(0, num_call_options):
            k = callK[n]
            vol = volatility_curve.volatility(k)
            opt = FXVanillaOption(self._maturity_dt, k, call_type)
            model = BlackScholes(vol)
            v = opt.value(value_dt, s0, discount_curve,
                          dividend_curve, model)
            piCall += v * self._callWts[n]

        pi = piCall + piPut
        optionTotal += g * pi
        var = optionTotal

        return var

###############################################################################

    def realised_variance(self, closePrices, use_logs=True):
        """ Calculate the realised variance according to market standard
        calculations which can either use log or percentage returns."""

        num_observations = len(closePrices)

        for i in range(0, num_observations):
            if closePrices[i] <= 0.0:
                raise FinError("Stock prices must be greater than zero")

        cumX2 = 0.0

        if use_logs is True:
            for i in range(1, num_observations):
                x = np.log(closePrices[i]/closePrices[i-1])
                cumX2 += x*x
        else:
            for i in range(1, num_observations):
                x = (closePrices[i]-closePrices[i-1])/closePrices[i-1]
                cumX2 += x*x

        var = cumX2 * 252.0 / num_observations
        return var


###############################################################################

    def print_strikes(self):

        if self._num_put_options == 0 and self._num_call_options == 0:
            return

        print("TYPE", "STRIKE", "WEIGHT")
        for n in range(0, self._num_put_options):
            k = self._put_strikes[n]
            wt = self._putWts[n]*self._notional
            print("PUT %7.2f %10.3f" % (k, wt))

        for n in range(0, self._num_call_options):
            k = self._call_strikes[n]
            wt = self._callWts[n]*self._notional
            print("CALL %7.2f %10.3f" % (k, wt))

###############################################################################
