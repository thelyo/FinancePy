##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################

from math import sqrt, log
from scipy import optimize

from ...utils.calendar import CalendarTypes
from ...utils.calendar import BusDayAdjustTypes, DateGenRuleTypes
from ...utils.day_count import DayCountTypes
from ...utils.frequency import FrequencyTypes
from ...utils.global_vars import gDaysInYear
from ...utils.math import ONE_MILLION, N
from ...products.credit.cds import CDS
from ...utils.helpers import check_argument_types
from ...utils.date import Date
from ...utils.error import FinError


###############################################################################


def fvol(volatility, *args):
    """ Root searching function in the calculation of the CDS implied
    volatility. """

    self = args[0]
    value_dt = args[1]
    issuer_curve = args[2]
    option_value = args[3]
    value = self.value(value_dt, issuer_curve, volatility)
    obj_fn = value - option_value
    return obj_fn


###############################################################################


class CDSOption:
    """ Class to manage the pricing and risk-management of an option on a
    single-name CDS. This is a contract in which the option buyer pays for an
    option to either buy or sell protection on the underlying CDS at a fixed
    spread agreed today and to be exercised in the future on a specified expiry
    date. The option may or may not cancel if there is a credit event before
    option expiry. This needs to be specified. """

    def __init__(self,
                 expiry_dt: Date,
                 maturity_dt: Date,
                 strike_coupon: float,
                 notional: float = ONE_MILLION,
                 long_protection: bool = True,
                 knockout_flag: bool = True,
                 freq_type: FrequencyTypes = FrequencyTypes.QUARTERLY,
                 dc_type: DayCountTypes = DayCountTypes.ACT_360,
                 cal_type: CalendarTypes = CalendarTypes.WEEKEND,
                 bd_type: BusDayAdjustTypes = BusDayAdjustTypes.FOLLOWING,
                 dg_type: DateGenRuleTypes = DateGenRuleTypes.BACKWARD):
        """ Create a FinCDSOption object with the option expiry date, the
        maturity date of the underlying CDS, the option strike coupon,
        notional, whether the option knocks out or not in the event of a credit
        event before expiry and the payment details of the underlying CDS. """

        check_argument_types(self.__init__, locals())

        if maturity_dt < expiry_dt:
            raise FinError("Maturity date must be after option expiry date")

        if strike_coupon < 0.0:
            raise FinError("Strike must be greater than zero")

        self._expiry_dt = expiry_dt
        self._maturity_dt = maturity_dt
        self._strike_coupon = strike_coupon
        self._long_protection = long_protection
        self._knockout_flag = knockout_flag
        self._notional = notional

        self._freq_type = freq_type
        self._dc_type = dc_type
        self._cal_type = cal_type
        self._bd_type = bd_type
        self._dg_type = dg_type

###############################################################################

    def value(self,
              value_dt,
              issuer_curve,
              volatility):
        """ Value the CDS option using Black's model with an adjustment for any
        Front End Protection.
        TODO - Should the CDS be created in the init method ? """

        if value_dt > self._expiry_dt:
            raise FinError("Expiry date is now or in the past")

        if volatility < 0.0:
            raise FinError("Volatility must be greater than zero")

        # The underlying is a forward starting option that steps in on
        # the expiry date and matures on the expiry date with a coupon
        # set equal to the option spread strike
        cds = CDS(self._expiry_dt,
                  self._maturity_dt,
                  self._strike_coupon,
                  self._notional,
                  self._long_protection,
                  self._freq_type,
                  self._dc_type,
                  self._cal_type,
                  self._bd_type,
                  self._dg_type)

        strike = self._strike_coupon
        forward_spread = cds.par_spread(value_dt, issuer_curve)
        forward_rpv01 = cds.risky_pv01(
            value_dt, issuer_curve)['dirty_rpv01']

        time_to_expiry = (self._expiry_dt - value_dt) / gDaysInYear
        logMoneyness = log(forward_spread / strike)

        halfVolSquaredT = 0.5 * volatility * volatility * time_to_expiry
        volSqrtT = volatility * sqrt(time_to_expiry)

        d1 = (logMoneyness + halfVolSquaredT) / volSqrtT
        d2 = (logMoneyness - halfVolSquaredT) / volSqrtT

        if self._long_protection:
            option_value = forward_spread * N(d1) - strike * N(d2)
        else:
            option_value = strike * N(-d2) - forward_spread * N(-d1)

        option_value = option_value * forward_rpv01

        # If the option does not knockout on a default before expiry then we
        # need to include the cost of protection which is provided between
        # the value date and the expiry date
        if self._knockout_flag is False and self._long_protection is True:
            df = issuer_curve.getDF(time_to_expiry)
            q = issuer_curve.getSurvProb(time_to_expiry)
            recovery = issuer_curve._recovery_rate
            frontEndProtection = df * (1.0 - q) * (1.0 - recovery)
            option_value += frontEndProtection

        # we return the option price in dollars
        return option_value * self._notional

###############################################################################

    def implied_volatility(self,
                           value_dt,
                           issuer_curve,
                           option_value):
        """ Calculate the implied CDS option volatility from a price. """
        arg_tuple = (self, value_dt, issuer_curve, option_value)
        sigma = optimize.newton(fvol, x0=0.3, args=arg_tuple, tol=1e-6,
                                maxiter=50)
        return sigma

###############################################################################
