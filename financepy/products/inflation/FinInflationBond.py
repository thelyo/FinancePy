###############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
###############################################################################

###############################################################################
# ADD Inflation assumption and resulting yield calculation
# Pricing using inflation curve and discount curve
###############################################################################


from ...utils.date import Date
from ...utils.error import FinError
from ...utils.frequency import annual_frequency, FrequencyTypes
from ...utils.calendar import CalendarTypes
from ...utils.day_count import DayCountTypes
from ...utils.helpers import label_to_string, check_argument_types
from ..bonds.bond import Bond, YTMCalcType

###############################################################################


class FinInflationBond(Bond):
    """ Class for inflation-linked bonds like TIPS and related analytics. These
    are bonds with coupon and principal adjusted by an index such as the CPI.
    We inherit from the Bond class. """

    def __init__(self,
                 issue_dt: Date,
                 maturity_dt: Date,
                 cpn: float,  # Annualised bond coupon before inflation
                 freq_type: FrequencyTypes,
                 dc_type: DayCountTypes,
                 ex_div_days: int,  # Value of CPI index at bond issue date
                 base_cpi_value: float,  # CPI value at issue
                 num_ex_dividend_days: int = 0,
                 cal_type: CalendarTypes = CalendarTypes.NONE):
        """ Create FinInflationBond object by providing Maturity, Frequency,
        coupon, frequency and the accrual convention type. You must also supply
        the base CPI used for all coupon and principal related calculations.
        The class inherits from Bond so has many similar functions. The YTM"""

        Bond.__init__(self, issue_dt, maturity_dt, cpn, freq_type,
                      dc_type, ex_div_days, cal_type)

        check_argument_types(self.__init__, locals())

        if issue_dt >= maturity_dt:
            raise FinError("Issue Date must preceded maturity date.")

        # If the maturity date falls on the last day of the month we assume
        # that earlier flows also fall on month ends
        self._end_of_month = False
        if maturity_dt.is_eom():
            self._end_of_month = True

        self._issue_dt = issue_dt
        self._maturity_dt = maturity_dt
        self._cpn = cpn
        self._freq_type = freq_type
        self._dc_type = dc_type
        self._freq = annual_frequency(freq_type)
        self._ex_div_days = ex_div_days  # This is the bond holding size
        self._base_cpi_value = base_cpi_value  # CPI value at issue date of bond
        self._par = 100.0  # This is how price is quoted
        self._redemption = 1.0  # Amount paid at maturity
        self._num_ex_dividend_days = num_ex_dividend_days
        self._inflation_accrued_interest = 0.0
        self._cal_type = cal_type
        self._cpn_dts = []
        self._flow_amounts = []

        self._settle_dt = Date(1, 1, 1900)
        self._accrued_interest = None
        self._accrued_days = 0.0
        self._alpha = 0.0

        self._calculate_cpn_dts()
        self._calculate_flows()

###############################################################################

    def inflation_principal(self,
                            settle_dt: Date,
                            face: (float),
                            ytm: float,
                            reference_cpi: float,
                            convention: YTMCalcType):
        """ Calculate the principal value of the bond based on the face
        amount and the CPI growth. """

        index_ratio = reference_cpi / self._base_cpi_value
        dirty_price = self.dirty_price_from_ytm(settle_dt, ytm,
                                                convention)
        principal = dirty_price * face / self._par
        principal = principal - self._accrued_interest
        principal *= index_ratio
        return principal

###############################################################################

    def flat_price_from_yield_to_maturity(self,
                                          settle_dt: Date,
                                          ytm: float,
                                          last_cpn_cpi: float,
                                          convention: YTMCalcType):
        """ Calculate the flat clean price value of the bond based on the clean
        price amount and the CPI growth to the last coupon date. """

        index_ratio = last_cpn_cpi / self._base_cpi_value
        clean_price = self.clean_price_from_ytm(
            settle_dt, ytm, convention)
        flat_price = clean_price
        flat_price *= index_ratio
        return flat_price

###############################################################################

    def inflation_accrued_interest(self, settle_dt: Date,
                                   face: (float),
                                   reference_cpi):
        """ Calculate the amount of coupon that has accrued between the
        previous coupon date and the settlement date. This is adjusted by the
        index ratio in line with the CPI growth since the bond base CPI date.
        We assume no ex-dividend period.
        """

        self.accrued_interest(settle_dt, face)
        index_ratio = reference_cpi / self._base_cpi_value
        self._inflation_accrued_interest = self._accrued_interest * index_ratio
        return self._inflation_accrued_interest

###############################################################################

    def __repr__(self):
        s = label_to_string("OBJECT TYPE", type(self).__name__)
        s += label_to_string("ISSUE DATE", self._issue_dt)
        s += label_to_string("MATURITY DATE", self._maturity_dt)
        s += label_to_string("COUPON", self._cpn)
        s += label_to_string("FREQUENCY", self._freq_type)
        s += label_to_string("DAY COUNT TYPE", self._dc_type)
        s += label_to_string("EX-DIV DAYS", self._ex_div_days)
        s += label_to_string("BASE CPI VALUE", self._base_cpi_value, "")
        return s

###############################################################################

    def _print(self):
        """ Print a list of the unadjusted coupon payment dates used in
        analytic calculations for the bond. """
        print(self)

###############################################################################
