##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################


import numpy as np

from ...utils.frequency import FrequencyTypes
from ...utils.global_vars import gDaysInYear
from ...utils.error import FinError
from ...utils.global_types import OptionTypes

from ...utils.helpers import label_to_string, check_argument_types
from ...utils.date import Date
from ...utils.day_count import DayCountTypes
from ...utils.calendar import BusDayAdjustTypes
from ...utils.calendar import CalendarTypes,  DateGenRuleTypes
from ...utils.schedule import Schedule
from ...products.equity.equity_option import EquityOption
from ...market.curves.discount_curve_flat import DiscountCurve

from ...models.black_scholes_analytic import bs_value
from ...models.black_scholes import BlackScholes
from ...models.model import Model

###############################################################################
# TODO: Do we need to day count adjust option payoffs ?
# TODO: Monte Carlo pricer
###############################################################################


class EquityCliquetOption(EquityOption):
    """ A EquityCliquetOption is a series of options which start and stop at
    successive times with each subsequent option resetting its strike to be ATM
    at the start of its life. This is also known as a reset option."""

    def __init__(self,
                 start_dt: Date,
                 final_expiry_dt: Date,
                 option_type: OptionTypes,
                 freq_type: FrequencyTypes,
                 day_count_type: DayCountTypes = DayCountTypes.THIRTY_E_360,
                 cal_type: CalendarTypes = CalendarTypes.WEEKEND,
                 bd_type: BusDayAdjustTypes = BusDayAdjustTypes.FOLLOWING,
                 dg_type: DateGenRuleTypes = DateGenRuleTypes.BACKWARD):
        """ Create the EquityCliquetOption by passing in the start date
        and the end date and whether it is a call or a put. Some additional
        data is needed in order to calculate the individual payments. """

        check_argument_types(self.__init__, locals())

        if option_type != OptionTypes.EUROPEAN_CALL and \
           option_type != OptionTypes.EUROPEAN_PUT:
            raise FinError("Unknown Option Type" + str(option_type))

        if final_expiry_dt < start_dt:
            raise FinError("Expiry date precedes start date")

        self._start_dt = start_dt
        self._final_expiry_dt = final_expiry_dt
        self._option_type = option_type
        self._freq_type = freq_type
        self._dc_type = day_count_type
        self._cal_type = cal_type
        self._bd_type = bd_type
        self._dg_type = dg_type

        self._expiry_dts = Schedule(self._start_dt,
                                    self._final_expiry_dt,
                                    self._freq_type,
                                    self._cal_type,
                                    self._bd_type,
                                    self._dg_type)._generate()

###############################################################################

    def value(self,
              value_dt: Date,
              stock_price: float,
              discount_curve: DiscountCurve,
              dividend_curve: DiscountCurve,
              model: Model):
        """ Value the cliquet option as a sequence of options using the Black-
        Scholes model. """

        if isinstance(value_dt, Date) is False:
            raise FinError("Valuation date is not a Date")

        if discount_curve._value_dt != value_dt:
            raise FinError(
                "Discount Curve valuation date not same as option value date")

        if dividend_curve._value_dt != value_dt:
            raise FinError(
                "Dividend Curve valuation date not same as option value date")

        if value_dt > self._final_expiry_dt:
            raise FinError("Value date after final expiry date.")

        s = stock_price
        v_cliquet = 0.0

        self._v_options = []
        self._dfs = []
        self._actualDates = []

        CALL = OptionTypes.EUROPEAN_CALL
        PUT = OptionTypes.EUROPEAN_PUT

        if isinstance(model, BlackScholes):

            v = model._volatility
            v = max(v, 1e-6)
            tprev = 0.0

            for dt in self._expiry_dts:

                if dt > value_dt:

                    df = discount_curve.df(dt)
                    t_exp = (dt - value_dt) / gDaysInYear
                    r = -np.log(df) / t_exp

                    # option life
                    tau = t_exp - tprev

                    # The deflator is out to the option reset time
                    dq = dividend_curve._df(tprev)

                    # The option dividend is over the option life
                    dqMat = dividend_curve._df(t_exp)

                    q = -np.log(dqMat/dq)/tau

                    if self._option_type == CALL:
                        v_fwd_opt = s * dq * \
                            bs_value(1.0, tau, 1.0, r, q, v, CALL.value)
                        v_cliquet += v_fwd_opt
                    elif self._option_type == PUT:
                        v_fwd_opt = s * dq * \
                            bs_value(1.0, tau, 1.0, r, q, v, PUT.value)
                        v_cliquet += v_fwd_opt
                    else:
                        raise FinError("Unknown option type")

#                    print(dt, r, df, q, v_fwd_opt, v_cliquet)

                    self._dfs.append(df)
                    self._v_options.append(v)
                    self._actualDates.append(dt)
                    tprev = t_exp
        else:
            raise FinError("Unknown Model Type")

        return v_cliquet

###############################################################################

    def print_payments(self):
        num_options = len(self._v_options)
        for i in range(0, num_options):
            print(self._actualDates[i], self._dfs[i], self._v_options[i])

###############################################################################

    def __repr__(self):
        s = label_to_string("OBJECT TYPE", type(self).__name__)
        s += label_to_string("START DATE", self._start_dt)
        s += label_to_string("FINAL EXPIRY DATE", self._final_expiry_dt)
        s += label_to_string("OPTION TYPE", self._option_type)
        s += label_to_string("FREQUENCY TYPE", self._freq_type)
        s += label_to_string("DAY COUNT TYPE", self._dc_type)
        s += label_to_string("CALENDAR TYPE", self._cal_type)
        s += label_to_string("BUS DAY ADJUST TYPE", self._bd_type)
        s += label_to_string("DATE GEN RULE TYPE",
                             self._dg_type, "")
        return s

###############################################################################

    def _print(self):
        """ Simple print function for backward compatibility. """
        print(self)

###############################################################################
