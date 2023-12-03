##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################

import numpy as np
from scipy import optimize
import copy

from ...utils.error import FinError
from ...utils.date import Date
from ...utils.helpers import label_to_string
from ...utils.helpers import check_argument_types, _func_name
from ...utils.global_vars import gDaysInYear
from ...market.curves.interpolator import InterpTypes, Interpolator
from ...market.curves.discount_curve import DiscountCurve
from ...products.rates.ibor_deposit import IborDeposit
from ...products.rates.ibor_fra import IborFRA
from ...products.rates.ibor_swap import IborSwap

swaptol = 1e-10

###############################################################################
# TODO: CHANGE times to df_times
###############################################################################


def _f(df, *args):
    """ Root search objective function for swaps """
    discount_curve = args[0]
    index_curve = args[1]
    value_dt = args[2]
    swap = args[3]

    num_points = len(index_curve._times)
    index_curve._dfs[num_points - 1] = df

    # For discount that need a fit function, we fit it now
    index_curve._interpolator.fit(index_curve._times, index_curve._dfs)
    v_swap = swap.value(value_dt, discount_curve, index_curve, None)

    notional = swap._fixed_leg._notional
    v_swap /= notional
    return v_swap

###############################################################################


def _g(df, *args):
    """ Root search objective function for swaps """

    discount_curve = args[0]
    curve = args[1]
    value_dt = args[2]
    fra = args[3]
    num_points = len(curve._times)
    curve._dfs[num_points - 1] = df

    # For discount that need a fit function, we fit it now
    curve._interpolator.fit(curve._times, curve._dfs)
    v_fra = fra.value(value_dt, discount_curve, curve)
    v_fra /= fra._notional
    return v_fra

###############################################################################


class IborDualCurve(DiscountCurve):
    """ Constructs an index curve as implied by the prices of Ibor
    deposits, FRAs and IRS. Discounting is assumed to be at a discount rate
    that is an input and usually derived from OIS rates. """

###############################################################################

    def __init__(self,
                 value_dt: Date,
                 discount_curve: DiscountCurve,
                 ibor_deposits: list,
                 ibor_fras: list,
                 ibor_swaps: list,
                 interp_type: InterpTypes = InterpTypes.FLAT_FWD_RATES,
                 check_refit: bool = False):  # Set to True to test it works
        """ Create an instance of a Ibor curve given a valuation date and
        a set of ibor deposits, ibor FRAs and ibor_swaps. Some of these may
        be left None and the algorithm will just use what is provided. An
        interpolation method has also to be provided. The default is to use a
        linear interpolation for swap rates on coupon dates and to then assume
        flat forwards between these coupon dates.

        The curve will assign a discount factor of 1.0 to the valuation date.
        """

        check_argument_types(getattr(self, _func_name(), None), locals())

        self._value_dt = value_dt
        self._discount_curve = discount_curve
        self._validate_inputs(ibor_deposits, ibor_fras, ibor_swaps)
        self._interp_type = interp_type
        self._check_refit = check_refit
        self._build_curve()

###############################################################################

    def _build_curve(self):
        """ Build curve based on interpolation. """

        self._build_curve_using_1d_solver()

###############################################################################

    def _validate_inputs(self,
                         ibor_deposits,
                         ibor_fras,
                         ibor_swaps):
        """ Validate the inputs for each of the Ibor products. """

        num_depos = len(ibor_deposits)
        num_fras = len(ibor_fras)
        num_swaps = len(ibor_swaps)

        depo_start_dt = self._value_dt
        swap_start_dt = self._value_dt

        if num_depos + num_fras + num_swaps == 0:
            raise FinError("No calibration instruments.")

        # Validation of the inputs.
        if num_depos > 0:

            depo_start_dt = ibor_deposits[0]._start_dt

            for depo in ibor_deposits:

                if isinstance(depo, IborDeposit) is False:
                    raise FinError("Deposit is not of type IborDeposit")

                start_dt = depo._start_dt

                if start_dt < self._value_dt:
                    raise FinError("First deposit starts before value date.")

                if start_dt < depo_start_dt:
                    depo_start_dt = start_dt

            for depo in ibor_deposits:
                start_dt = depo._start_dt
                endDt = depo._maturity_dt
                if start_dt >= endDt:
                    raise FinError("First deposit ends on or before it begins")

        # Ensure order of depos
        if num_depos > 1:

            prev_dt = ibor_deposits[0]._maturity_dt
            for depo in ibor_deposits[1:]:
                next_dt = depo._maturity_dt
                if next_dt <= prev_dt:
                    raise FinError("Deposits must be in increasing maturity")
                prev_dt = next_dt

        # REMOVED THIS AS WE WANT TO ANCHOR CURVE AT VALUATION DATE
        # USE A SYNTHETIC DEPOSIT TO BRIDGE GAP FROM VALUE DATE TO SETTLEMENT DATE
        # Ensure that valuation date is on or after first deposit start date
        # if num_depos > 1:
        #    if ibor_deposits[0]._effective_dt > self._value_dt:
        #        raise FinError("Valuation date must not be before first deposit settles.")

        if num_fras > 0:
            for fra in ibor_fras:
                if isinstance(fra, IborFRA) is False:
                    raise FinError("FRA is not of type IborFRA")

                start_dt = fra._start_dt
                if start_dt <= self._value_dt:
                    raise FinError("FRAs starts before valuation date")

        if num_fras > 1:
            prev_dt = ibor_fras[0]._maturity_dt
            for fra in ibor_fras[1:]:
                next_dt = fra._maturity_dt
                if next_dt <= prev_dt:
                    raise FinError("FRAs must be in increasing maturity")
                prev_dt = next_dt

        if num_swaps > 0:

            swap_start_dt = ibor_swaps[0]._effective_dt

            for swap in ibor_swaps:

                if isinstance(swap, IborSwap) is False:
                    raise FinError("Swap is not of type IborSwap")

                start_dt = swap._effective_dt
                if start_dt < self._value_dt:
                    raise FinError("Swaps starts before valuation date.")

                if swap._effective_dt < swap_start_dt:
                    swap_start_dt = swap._effective_dt

        if num_swaps > 1:

            # Swaps must all start on the same date for the bootstrap
            start_dt = ibor_swaps[0]._effective_dt
            for swap in ibor_swaps[1:]:
                next_start_dt = swap._effective_dt
                if next_start_dt != start_dt:
                    raise FinError("Swaps must all have same start date.")

            # Swaps must be increasing in tenor/maturity
            prev_dt = ibor_swaps[0]._maturity_dt
            for swap in ibor_swaps[1:]:
                next_dt = swap._maturity_dt
                if next_dt <= prev_dt:
                    raise FinError("Swaps must be in increasing maturity")
                prev_dt = next_dt

            # Swaps must have same cash flows for bootstrap to work
            longestSwap = ibor_swaps[-1]
            longestSwapCpnDates = longestSwap._fixed_leg._payment_dts
            for swap in ibor_swaps[0:-1]:
                swapCpnDates = swap._fixed_leg._payment_dts
                num_flows = len(swapCpnDates)
                for iFlow in range(0, num_flows):
                    if swapCpnDates[iFlow] != longestSwapCpnDates[iFlow]:
                        raise FinError(
                            "Swap coupons are not on the same date grid.")

        #######################################################################
        # Now we have ensure they are in order check for overlaps and the like
        #######################################################################

        lastDepositMaturityDate = Date(1, 1, 1900)
        firstFRAMaturityDate = Date(1, 1, 1900)
        lastFRAMaturityDate = Date(1, 1, 1900)

        if num_depos > 0:
            lastDepositMaturityDate = ibor_deposits[-1]._maturity_dt

        if num_fras > 0:
            firstFRAMaturityDate = ibor_fras[0]._maturity_dt
            lastFRAMaturityDate = ibor_fras[-1]._maturity_dt

        if num_swaps > 0:
            first_swap_maturity_dt = ibor_swaps[0]._maturity_dt

        if num_depos > 0 and num_fras > 0:
            if firstFRAMaturityDate <= lastDepositMaturityDate:
                print("FRA Maturity Date:", firstFRAMaturityDate)
                print("Last Deposit Date:", lastDepositMaturityDate)
                raise FinError("First FRA must end after last Deposit")

        if num_fras > 0 and num_swaps > 0:
            if first_swap_maturity_dt <= lastFRAMaturityDate:
                raise FinError("First Swap must mature after last FRA")

        # If both depos and swaps start after T, we need a rate to get them to
        # the first deposit. So we create a synthetic deposit rate contract.

        if swap_start_dt > self._value_dt:

            if num_depos == 0:
                raise FinError("Need a deposit rate to pin down short end.")

            if depo_start_dt > self._value_dt:
                firstDepo = ibor_deposits[0]
                if firstDepo._start_dt > self._value_dt:
                    print("Inserting synthetic deposit")
                    syntheticDeposit = copy.deepcopy(firstDepo)
                    syntheticDeposit._start_dt = self._value_dt
                    syntheticDeposit._maturity_dt = firstDepo._start_dt
                    ibor_deposits.insert(0, syntheticDeposit)
                    num_depos += 1

        # Now determine which instruments are used
        self._usedDeposits = ibor_deposits
        self._usedFRAs = ibor_fras
        self._usedSwaps = ibor_swaps

        # Need the floating leg basis for the curve
        if len(self._usedSwaps) > 0:
            self._dc_type = ibor_swaps[0]._float_leg._dc_type
        else:
            self._dc_type = None

###############################################################################

    def _build_curve_using_1d_solver(self):
        """ Construct the discount curve using a bootstrap approach. This is
        the non-linear slower method that allows the user to choose a number
        of interpolation approaches between the swap rates and other rates. It
        involves the use of a solver. """

        self._interpolator = Interpolator(self._interp_type)

        self._times = np.array([])
        self._dfs = np.array([])

        # time zero is now.
        tmat = 0.0
        df_mat = 1.0
        self._times = np.append(self._times, 0.0)
        self._dfs = np.append(self._dfs, df_mat)
        self._interpolator.fit(self._times, self._dfs)

        # A deposit is not margined and not indexed to Libor so should
        # probably not be used to build an indexed Libor curve from
        for depo in self._usedDeposits:

            df_settle = self.df(depo._start_dt)
            df_mat = depo._maturity_df() * df_settle
            tmat = (depo._maturity_dt - self._value_dt) / gDaysInYear
            self._times = np.append(self._times, tmat)
            self._dfs = np.append(self._dfs, df_mat)
            self._interpolator.fit(self._times, self._dfs)

        oldtmat = tmat

        for fra in self._usedFRAs:

            tset = (fra._start_dt - self._value_dt) / gDaysInYear
            tmat = (fra._maturity_dt - self._value_dt) / gDaysInYear

            # if both dates are after the previous FRA/FUT then need to
            # solve for 2 discount factors simultaneously using root search

            if tset < oldtmat and tmat > oldtmat:
                df_mat = fra.maturity_df(self)
                self._times = np.append(self._times, tmat)
                self._dfs = np.append(self._dfs, df_mat)
            else:
                self._times = np.append(self._times, tmat)
                self._dfs = np.append(self._dfs, df_mat)
                argtuple = (self._discount_curve, self,
                            self._value_dt, fra)
                df_mat = optimize.newton(_g, x0=df_mat, fprime=None,
                                        args=argtuple, tol=swaptol,
                                        maxiter=50, fprime2=None)

        for swap in self._usedSwaps:
            # I use the lastPaymentDate in case a date has been adjusted fwd
            # over a holiday as the maturity date is usually not adjusted CHECK
            maturity_dt = swap._fixed_leg._payment_dts[-1]
            tmat = (maturity_dt - self._value_dt) / gDaysInYear

            self._times = np.append(self._times, tmat)
            self._dfs = np.append(self._dfs, df_mat)

            argtuple = (self._discount_curve, self, self._value_dt, swap)

            df_mat = optimize.newton(_f, x0=df_mat, fprime=None, args=argtuple,
                                    tol=swaptol, maxiter=50, fprime2=None,
                                    full_output=False)

        if self._check_refit is True:
            self._check_refits(1e-10, swaptol, 1e-5)

###############################################################################

    # def _build_curve_linear_swap_rate_interpolation(self):
    #     """ Construct the discount curve using a bootstrap approach. This is
    #     the linear swap rate method that is fast and exact as it does not
    #     require the use of a solver. It is also market standard. """

    #     self._interpolator = Interpolator(self._interp_type)

    #     self._times = np.array([])
    #     self._dfs = np.array([])

    #     # time zero is now.
    #     tmat = 0.0
    #     df_mat = 1.0
    #     self._times = np.append(self._times, 0.0)
    #     self._dfs = np.append(self._dfs, df_mat)
    #     self._interpolator.fit(self._times, self._dfs)

    #     for depo in self._usedDeposits:
    #         df_settle = self.df(depo._effective_dt)
    #         df_mat = depo._maturity_df() * df_settle
    #         tmat = (depo._maturity_dt - self._value_dt) / gDaysInYear
    #         self._times = np.append(self._times, tmat)
    #         self._dfs = np.append(self._dfs, df_mat)
    #         self._interpolator.fit(self._times, self._dfs)

    #     oldtmat = tmat

    #     for fra in self._usedFRAs:

    #         tset = (fra._start_dt - self._value_dt) / gDaysInYear
    #         tmat = (fra._maturity_dt - self._value_dt) / gDaysInYear

    #         # if both dates are after the previous FRA/FUT then need to
    #         # solve for 2 discount factors simultaneously using root search

    #         if tset < oldtmat and tmat > oldtmat:
    #             df_mat = fra.maturity_df(self)
    #             self._times = np.append(self._times, tmat)
    #             self._dfs = np.append(self._dfs, df_mat)
    #             self._interpolator.fit(self._times, self._dfs)
    #         else:
    #             self._times = np.append(self._times, tmat)
    #             self._dfs = np.append(self._dfs, df_mat)
    #             self._interpolator.fit(self._times, self._dfs)

    #             argtuple = (self._discount_curve, self, self._value_dt, fra)
    #             df_mat = optimize.newton(_g, x0=df_mat, fprime=None,
    #                                     args=argtuple, tol=swaptol,
    #                                     maxiter=50, fprime2=None)

    #     if len(self._usedSwaps) == 0:
    #         if self._check_refit is True:
    #             self._check_refits(1e-10, swaptol, 1e-5)
    #         return

    #     #######################################################################
    #     # ADD SWAPS TO CURVE
    #     #######################################################################

    #     # Find where the FRAs and Depos go up to as this bit of curve is done
    #     foundStart = False
    #     lastDate = self._value_dt
    #     if len(self._usedDeposits) != 0:
    #         lastDate = self._usedDeposits[-1]._maturity_dt

    #     if len(self._usedFRAs) != 0:
    #         lastDate = self._usedFRAs[-1]._maturity_dt

    #     # We use the longest swap assuming it has a superset of ALL of the
    #     # swap flow dates used in the curve construction
    #     longestSwap = self._usedSwaps[-1]
    #     cpn_dts = longestSwap._adjusted_fixed_dts
    #     num_flows = len(cpn_dts)

    #     # Find where first coupon without discount factor starts
    #     start_index = 0
    #     for i in range(0, num_flows):
    #         if cpn_dts[i] > lastDate:
    #             start_index = i
    #             foundStart = True
    #             break

    #     if foundStart is False:
    #         raise FinError("Found start is false. Swaps payments inside FRAs")

    #     swap_rates = []
    #     swap_times = []

    #     # I use the last coupon date for the swap rate interpolation as this
    #     # may be different from the maturity date due to a holiday adjustment
    #     # and the swap rates need to align with the coupon payment dates
    #     for swap in self._usedSwaps:
    #         swap_rate = swap._fixed_coupon
    #         maturity_dt = swap._adjusted_fixed_dts[-1]
    #         tswap = (maturity_dt - self._value_dt) / gDaysInYear
    #         swap_times.append(tswap)
    #         swap_rates.append(swap_rate)

    #     interpolatedSwapRates = [0.0]
    #     interpolatedswap_times = [0.0]

    #     for dt in cpn_dts[1:]:
    #         swapTime = (dt - self._value_dt) / gDaysInYear
    #         swap_rate = np.interp(swapTime, swap_times, swap_rates)
    #         interpolatedSwapRates.append(swap_rate)
    #         interpolatedswap_times.append(swapTime)

    #     # Do I need this line ?
    #     interpolatedSwapRates[0] = interpolatedSwapRates[1]

    #     accrual_factors = longestSwap._fixedYearFracs

    #     acc = 0.0
    #     df = 1.0
    #     pv01 = 0.0
    #     df_settle = self.df(longestSwap._effective_dt)

    #     for i in range(1, start_index):
    #         dt = cpn_dts[i]
    #         df = self.df(dt)
    #         acc = accrual_factors[i-1]
    #         pv01 += acc * df

    #     for i in range(start_index, num_flows):

    #         dt = cpn_dts[i]
    #         tmat = (dt - self._value_dt) / gDaysInYear
    #         swap_rate = interpolatedSwapRates[i]
    #         acc = accrual_factors[i-1]
    #         pv01End = (acc * swap_rate + 1.0)
    #         df_mat = (df_settle - swap_rate * pv01) / pv01End

    #         self._times = np.append(self._times, tmat)
    #         self._dfs = np.append(self._dfs, df_mat)
    #         self._interpolator.fit(self._times, self._dfs)

    #         pv01 += acc * df_mat

    #     if self._check_refit is True:
    #         self._check_refits(1e-10, swaptol, 1e-5)

###############################################################################

    def _check_refits(self, depoTol, fraTol, swapTol):
        """ Ensure that the Ibor curve refits the calibration instruments. """
        for depo in self._usedDeposits:
            v = depo.value(self._value_dt, self) / depo._notional
            if abs(v - 1.0) > depoTol:
                print("Value", v)
                raise FinError("Deposit not repriced.")

        for fra in self._usedFRAs:
            v = fra.value(self._value_dt,
                          self._discount_curve, self) / fra._notional
            if abs(v) > fraTol:
                print("Value", v)
                raise FinError("FRA not repriced.")

        for swap in self._usedSwaps:
            # We value it as of the start date of the swap
            v = swap.value(swap._effective_dt, self._discount_curve,
                           self, None)
            v = v / swap._fixed_leg._notional
            if abs(v) > swapTol:
                print("Swap with maturity " + str(swap._maturity_dt)
                      + " Not Repriced. Has Value", v)
                swap.print_fixed_leg_pv()
                swap.print_float_leg_pv()
                raise FinError("Swap not repriced.")

###############################################################################

    def __repr__(self):
        """ Print out the details of the Ibor curve. """

        s = label_to_string("OBJECT TYPE", type(self).__name__)
        s += label_to_string("VALUATION DATE", self._value_dt)

        for depo in self._usedDeposits:
            s += label_to_string("DEPOSIT", "")
            s += depo.__repr__()

        for fra in self._usedFRAs:
            s += label_to_string("FRA", "")
            s += fra.__repr__()

        for swap in self._usedSwaps:
            s += label_to_string("SWAP", "")
            s += swap.__repr__()

        num_points = len(self._times)

        s += label_to_string("INTERP TYPE", self._interp_type)
        s += label_to_string("GRID TIMES", "GRID DFS")

        for i in range(0, num_points):
            s += label_to_string("% 10.6f" % self._times[i],
                                 "%12.10f" % self._dfs[i])
        return s

###############################################################################

    def _print(self):
        """ Simple print function for backward compatibility. """
        print(self)

###############################################################################
