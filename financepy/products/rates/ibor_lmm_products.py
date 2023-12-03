##############################################################################
# Copyright (C) 2018, 2019, 2020 Dominic O'Kane
##############################################################################

# TODO: Extend to allow term structure of volatility
# TODO: Extend to allow two fixed legs in underlying swap
# TODO: Cash settled swaptions

""" This module implements the LMM in the spot measure. It combines both model
and product specific code - I am not sure if it is better to separate these. At
the moment this seems to work ok.

THIS IS STILL IN PROTOPTYPE MODE. DO NOT USE. """

import numpy as np

from ...utils.calendar import CalendarTypes
from ...utils.calendar import BusDayAdjustTypes
from ...utils.calendar import DateGenRuleTypes
from ...utils.day_count import DayCountTypes
from ...utils.frequency import FrequencyTypes
from ...utils.day_count import DayCount
from ...utils.schedule import Schedule
from ...utils.error import FinError
from ...utils.helpers import check_argument_types
from ...utils.date import Date

from ...models.lmm_mc import lmm_simulate_fwds_1f
from ...models.lmm_mc import lmm_simulate_fwds_mf
from ...models.lmm_mc import lmm_simulate_fwds_nf
from ...models.lmm_mc import ModelLMMModelTypes
from ...models.lmm_mc import lmm_cap_flr_pricer

from ...utils.global_vars import gDaysInYear
from ...utils.math import ONE_MILLION

from ...utils.global_types import SwapTypes
from ...utils.global_types import FinCapFloorTypes

from financepy.market.volatility.ibor_cap_vol_curve import IborCapVolCurve

###############################################################################


class IborLMMProducts():
    """ This is the class for pricing Ibor products using the LMM. """

    def __init__(self,
                 settle_dt: Date,
                 maturity_dt: Date,
                 float_freq_type: FrequencyTypes = FrequencyTypes.QUARTERLY,
                 float_dc_type: DayCountTypes = DayCountTypes.THIRTY_E_360,
                 cal_type: CalendarTypes = CalendarTypes.WEEKEND,
                 bd_type: BusDayAdjustTypes = BusDayAdjustTypes.FOLLOWING,
                 dg_type: DateGenRuleTypes = DateGenRuleTypes.BACKWARD):
        """ Create a European-style swaption by defining the exercise date of
        the swaption, and all of the details of the underlying interest rate
        swap including the fixed coupon and the details of the fixed and the
        floating leg payment schedules. """

        check_argument_types(self.__init__, locals())

        if settle_dt > maturity_dt:
            raise FinError("Settlement date must be before maturity date")

        """ Set up the grid for the Ibor rates that are to be simulated. These
        must be consistent with the floating rate leg of the product that is to
        be priced. """

        self._start_dt = settle_dt
        self._gridDates = Schedule(settle_dt,
                                   maturity_dt,
                                   float_freq_type,
                                   cal_type,
                                   bd_type,
                                   dg_type)._generate()

        self._accrual_factors = []
        self._float_dc_type = float_dc_type

        basis = DayCount(self._float_dc_type)
        prev_dt = self._gridDates[0]

        self._gridTimes = [0.0]

        for next_dt in self._gridDates[1:]:
            tau = basis.year_frac(prev_dt, next_dt)[0]
            t = (next_dt - self._gridDates[0]) / gDaysInYear
            self._accrual_factors.append(tau)
            self._gridTimes.append(t)
            prev_dt = next_dt

#        print(self._gridTimes)
        self._accrual_factors = np.array(self._accrual_factors)
        self._num_fwds = len(self._accrual_factors)
        self._fwds = None

#        print("Num FORWARDS", self._num_fwds)

###############################################################################

    def simulate_1f(self,
                    discount_curve,
                    vol_curve: IborCapVolCurve,
                    num_paths: int = 1000,
                    numeraireIndex: int = 0,
                    useSobol: bool = True,
                    seed: int = 42):
        """ Run the one-factor simulation of the evolution of the forward
        Ibors to generate and store all of the Ibor forward rate paths. """

        if num_paths < 2 or num_paths > 1000000:
            raise FinError("NumPaths must be between 2 and 1 million")

        if discount_curve._value_dt != self._start_dt:
            raise FinError("Curve anchor date not the same as LMM start date.")

        self._num_paths = num_paths
        self._numeraire_index = numeraireIndex
        self._use_sobol = useSobol

        num_grid_points = len(self._gridDates)

        self._num_fwds = num_grid_points
        self._forwardCurve = []

        for i in range(1, num_grid_points):
            start_dt = self._gridDates[i-1]
            end_dt = self._gridDates[i]
            fwd_rate = discount_curve.fwd_rate(start_dt,
                                               end_dt,
                                               self._float_dc_type)
            self._forwardCurve.append(fwd_rate)

        self._forwardCurve = np.array(self._forwardCurve)

        gammas = np.zeros(num_grid_points)
        for ix in range(1, num_grid_points):
            dt = self._gridDates[ix]
            gammas[ix] = vol_curve.caplet_vol(dt)

        self._fwds = lmm_simulate_fwds_1f(self._num_fwds,
                                          num_paths,
                                          numeraireIndex,
                                          self._forwardCurve,
                                          gammas,
                                          self._accrual_factors,
                                          useSobol,
                                          seed)

###############################################################################

    def simulate_mf(self,
                    discount_curve,
                    numFactors: int,
                    lambdas: np.ndarray,
                    num_paths: int = 10000,
                    numeraireIndex: int = 0,
                    useSobol: bool = True,
                    seed: int = 42):
        """ Run the simulation to generate and store all of the Ibor forward
        rate paths. This is a multi-factorial version so the user must input
        a numpy array consisting of a column for each factor and the number of
        rows must equal the number of grid times on the underlying simulation
        grid. CHECK THIS. """

#        check_argument_types(self.__init__, locals())

        if num_paths < 2 or num_paths > 1000000:
            raise FinError("NumPaths must be between 2 and 1 million")

        if discount_curve._curve_dt != self._start_dt:
            raise FinError("Curve anchor date not the same as LMM start date.")

        print("LEN LAMBDAS", len(lambdas))
        print("LEN", len(lambdas[0]))
        # We pass a vector of vol discount, one for each factor
        if numFactors != len(lambdas):
            raise FinError("Lambda doesn't have specified number of factors.")

        numRows = len(lambdas[0])
        if numRows != self._num_fwds+1:
            raise FinError("Vol Components needs same number of rows as grid")

        self._num_paths = num_paths
        self._numeraire_index = numeraireIndex
        self._use_sobol = useSobol

        self._num_fwds = len(self._gridDates) - 1
        self._forwardCurve = []

        for i in range(1, self._num_fwds):
            start_dt = self._gridDates[i-1]
            end_dt = self._gridDates[i]
            fwd_rate = discount_curve.fwd_rate(start_dt, end_dt,
                                               self._float_dc_type)
            self._forwardCurve.append(fwd_rate)

        self._forwardCurve = np.array(self._forwardCurve)

        self._fwds = lmm_simulate_fwds_mf(self._num_fwds,
                                          numFactors,
                                          num_paths,
                                          numeraireIndex,
                                          self._forwardCurve,
                                          lambdas,
                                          self._accrual_factors,
                                          useSobol,
                                          seed)

###############################################################################

    def simulate_nf(self,
                    discount_curve,
                    vol_curve: IborCapVolCurve,
                    corr_matrix: np.ndarray,
                    model_type: ModelLMMModelTypes,
                    num_paths: int = 1000,
                    numeraire_index: int = 0,
                    use_sobol: bool = True,
                    seed: int = 42):
        """ Run the simulation to generate and store all of the Ibor forward
        rate paths using a full factor reduction of the fwd-fwd correlation
        matrix using Cholesky decomposition."""

        check_argument_types(self.__init__, locals())

        if num_paths < 2 or num_paths > 1000000:
            raise FinError("NumPaths must be between 2 and 1 million")

        if isinstance(model_type, ModelLMMModelTypes) is False:
            raise FinError("Model type must be type FinRateModelLMMModelTypes")

        if discount_curve.curve_dt != self._start_dt:
            raise FinError("Curve anchor date not the same as LMM start date.")

        self._num_paths = num_paths
        self._vol_curves = vol_curve
        self._corr_matrix = corr_matrix
        self._modelType = model_type
        self._numeraire_index = numeraire_index
        self._use_sobol = use_sobol

        num_grid_points = len(self._gridTimes)

        self._num_fwds = num_grid_points - 1
        self._fwd_curve = []

        for i in range(1, num_grid_points):
            start_dt = self._gridDates[i-1]
            end_dt = self._gridDates[i]
            fwd_rate = discount_curve.forward_rate(start_dt,
                                                   end_dt,
                                                   self._float_dc_type)
            self._fwd_curve.append(fwd_rate)

        self._fwd_curve = np.array(self._fwd_curve)

        zetas = np.zeros(num_grid_points)
        for ix in range(1, num_grid_points):
            dt = self._gridDates[ix]
            zetas[ix] = vol_curve.caplet_vol(dt)

        # This function does not use Sobol - TODO
        self._fwds = lmm_simulate_fwds_nf(self._num_fwds,
                                          num_paths,
                                          self._fwd_curve,
                                          zetas,
                                          corr_matrix,
                                          self._accrual_factors,
                                          seed)

###############################################################################

    def value_swaption(self,
                       settle_dt: Date,
                       exercise_dt: Date,
                       maturity_dt: Date,
                       swaptionType: SwapTypes,
                       fixed_coupon: float,
                       fixed_freq_type: FrequencyTypes,
                       fixed_dc_type: DayCountTypes,
                       notional: float = ONE_MILLION,
                       float_freq_type: FrequencyTypes = FrequencyTypes.QUARTERLY,
                       float_dc_type: DayCountTypes = DayCountTypes.THIRTY_E_360,
                       cal_type: CalendarTypes = CalendarTypes.WEEKEND,
                       bd_type: BusDayAdjustTypes = BusDayAdjustTypes.FOLLOWING,
                       dg_type: DateGenRuleTypes = DateGenRuleTypes.BACKWARD):
        """ Value a swaption in the LMM model using simulated paths of the
        forward curve. This relies on pricing the fixed leg of the swap and
        assuming that the floating leg will be worth par. As a result we only
        need simulate Ibors with the frequency of the fixed leg. """

        # Note that the simulation time steps run all the way out to the last
        # forward rate. However we only really need the forward rates at the
        # expiry date of the option. It may be worth amending the simulate
        # code to impose a limit on the time steps in order to speed up the
        # overall pricing if it requires a new run every time. However once
        # generated, the speed of pricing is not affected so this is not
        # strictly an urgent issue.

        swaption_float_dts = Schedule(settle_dt,
                                      maturity_dt,
                                      float_freq_type,
                                      cal_type,
                                      bd_type,
                                      dg_type)._generate()

        for swaptionDt in swaption_float_dts:
            foundDt = False
            for gridDt in self._gridDates:
                if swaptionDt == gridDt:
                    foundDt = True
                    break
            if foundDt is False:
                raise FinError("Swaption float leg not on grid.")

        swaptionFixedDates = Schedule(settle_dt,
                                      maturity_dt,
                                      fixed_freq_type,
                                      cal_type,
                                      bd_type,
                                      dg_type)._generate()

        for swaptionDt in swaptionFixedDates:
            foundDt = False
            for gridDt in self._gridDates:
                if swaptionDt == gridDt:
                    foundDt = True
                    break
            if foundDt is False:
                raise FinError("Swaption fixed leg not on grid.")

        a = 0
        b = 0

        for gridDt in self._gridDates:
            if gridDt == exercise_dt:
                break
            else:
                a += 1

        for gridDt in self._gridDates:
            if gridDt == maturity_dt:
                break
            else:
                b += 1

        if b == 0:
            raise FinError("Swaption swap maturity date is today.")

#        num_paths = 1000
#        v = LMMSwaptionPricer(fixed_coupon, a, b, num_paths,
#                              fwd0, fwds, taus, isPayer)
        v = 0.0
        return v

###############################################################################

    def value_cap_floor(self,
                        settle_dt: Date,
                        maturity_dt: Date,
                        cap_floor_type: FinCapFloorTypes,
                        cap_floor_rate: float,
                        freq_type: FrequencyTypes = FrequencyTypes.QUARTERLY,
                        dc_type: DayCountTypes = DayCountTypes.ACT_360,
                        notional: float = ONE_MILLION,
                        cal_type: CalendarTypes = CalendarTypes.WEEKEND,
                        bd_type: BusDayAdjustTypes = BusDayAdjustTypes.FOLLOWING,
                        dg_type: DateGenRuleTypes = DateGenRuleTypes.BACKWARD):
        """ Value a cap or floor in the LMM. """

        cap_floor_dts = Schedule(settle_dt,
                                 maturity_dt,
                                 freq_type,
                                 cal_type,
                                 bd_type,
                                 dg_type)._generate()

        for cap_floorlet_dt in cap_floor_dts:
            foundDt = False
            for gridDt in self._gridDates:
                if cap_floorlet_dt == gridDt:
                    foundDt = True
                    break
            if foundDt is False:
                raise FinError("CapFloor date not on grid.")

        numFowards = len(cap_floor_dts)
        num_paths = self._num_paths
        K = cap_floor_rate

        is_cap = 0
        if cap_floor_type == FinCapFloorTypes.CAP:
            is_cap = 1

        fwd0 = self._fwd_curve
        fwds = self._fwds
        taus = self._accrual_factors

        v = lmm_cap_flr_pricer(numFowards, num_paths, K,
                               fwd0, fwds, taus, is_cap)

        # Sum the cap/floorlets to get cap/floor value
        v_capFloor = 0.0
        for v_capFloorLet in v:
            v_capFloor += v_capFloorLet * notional

        return v_capFloor

###############################################################################

    def __repr__(self):
        """ Function to allow us to print the LMM Products details. """

        s = "Function not written"
        return s

###############################################################################

    def _print(self):
        """ Alternative print method. """

        print(self)

###############################################################################
