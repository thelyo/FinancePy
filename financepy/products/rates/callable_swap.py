# ##############################################################################
# # Copyright (C) 2018, 2019, 2020 Dominic O'Kane
# ##############################################################################

# from ...utils.FinGlobalVariables import gDaysInYear
# from ...models.HWTree import HWTree
# from ...models.BKTree import BKTree
# from ...utils.FinError import FinError
# from ...utils.FinFrequency import FrequencyTypes
# from ...utils.FinDayCount import FinDayCount
# from ...utils.FinDayCount import DayCountTypes
# from ...products.bonds.Bond import Bond


# from ...utils.Date import Date
# from ...utils.FinCalendar import Calendar, CalendarTypes
# from ...utils.FinCalendar import BusDayAdjustTypes, DateGenRuleTypes
# from ...utils.FinSchedule import FinSchedule
# from ...utils.FinMath import ONE_MILLION

# from ...utils.FinHelperFunctions import label_to_string

# from enum import Enum
# import numpy as np

# ###############################################################################


# class FinSwaptionModelTypes(Enum):
#     HULL_WHITE = 1
#     BLACK_KARASINSKI = 2

# ###############################################################################


# class BondOptionTypes(Enum):
#     EUROPEAN_CALL = 1
#     EUROPEAN_PUT = 2
#     AMERICAN_CALL = 3
#     AMERICAN_PUT = 4


# class FinSwaptionTypes(Enum):
#     PAY = 1
#     RECEIVE = 2

# class FinSwaptionExerciseTypes(Enum):
#     EUROPEAN = 1
#     BERMUDAN = 2

# ###############################################################################


# class IborBermudanSwaption
#     """ Class for fixed coupon bonds with embedded call or put optionality. """

#     def __init__(self,
#                  exercise_dt,
#                  exercise_type,
#                  maturity_dt,
#                  swaptionType,
#                  fixed_coupon,
#                  fixed_freq_type,
#                  fixed_dc_type,
#                  notional=ONE_MILLION,
#                  float_freq_type=FrequencyTypes.QUARTERLY,
#                  float_dc_type=DayCountTypes.THIRTY_E_360,
#                  cal_type=CalendarTypes.WEEKEND,
#                  bd_type=BusDayAdjustTypes.FOLLOWING,
#                  dg_type=DateGenRuleTypes.BACKWARD):
#         """ Create a Bermudan swaption contract. This is an option to enter
#         into a swap at a fixed coupon on all of the fixed leg coupon dates
#         until the exercise date. """

#         if exercise_dt > maturity_dt:
#             raise FinError("Exercise date must be before swap maturity date")

#         if exercise_type not in FinSwaptionExerciseTypes:
#             raise FinError("Exercise type must be a FinSwaptionExerciseTypes")

#         if fixed_dc_type not in DayCountTypes:
#             raise FinError(
#                 "Unknown Fixed Day Count Rule type " +
#                 str(fixed_dc_type))

#         if fixed_freq_type not in FrequencyTypes:
#             raise FinError(
#                 "Unknown Fixed Frequency type " +
#                 str(fixed_freq_type))

#         if float_dc_type not in DayCountTypes:
#             raise FinError(
#                 "Unknown Float Day Count Rule type " +
#                 str(float_dc_type))

#         if float_freq_type not in FrequencyTypes:
#             raise FinError(
#                 "Unknown Float Frequency type " +
#                 str(fixed_freq_type))

#         if cal_type not in CalendarTypes:
#             raise FinError("Unknown Calendar type " + str(cal_type))

#         if bd_type not in BusDayAdjustTypes:
#             raise FinError(
#                 "Unknown Business Day Adjust type " +
#                 str(bd_type))

#         if dg_type not in DateGenRuleTypes:
#             raise FinError(
#                 "Unknown Date Gen Rule type " +
#                 str(dg_type))

#         self._exercise_dt = exercise_dt
#         self._maturity_dt = maturity_dt
#         self._fixed_coupon = fixed_coupon
#         self._fixed_freq_type = fixed_freq_type
#         self._fixed_dc_type = fixed_dc_type
#         self._notional = notional
#         self._float_freq_type = float_freq_type
#         self._float_dc_type = float_dc_type

#         self._cal_type = cal_type
#         self._bd_type = bd_type
#         self._dg_type = dg_type

#         self._pv01 = None
#         self._fwd_swap_rate = None
#         self._forward_df = None
#         self._underlying_swap = None

# ###############################################################################

#     def value(self,
#               value_dt,
#               discount_curve,
#               model):
#         """ Value the bermuda swaption. This is done using the specified
#         model and a discount curve. """

#         float_spread = 0.0
#         payFixedFlag = True

#         # The underlying is a swap in which we pay the fixed amount
#         swap = IborSwap(self._exercise_dt,
#                             self._maturity_dt,
#                             self._fixed_coupon,
#                             self._fixed_freq_type,
#                             self._fixed_dc_type,
#                             self._notional,
#                             float_spread,
#                             self._float_freq_type,
#                             self._float_dc_type,
#                             payFixedFlag,
#                             self._cal_type,
#                             self._bd_type,
#                             self._dg_type)

#         swap.generate_flows()
#         cpn_times = []
#         cpn_amounts = []

#         for i_flow in range(1, len(self._swap._adjusted_fixed_dts)):
#             flow_dt= swap._adjusted_fixed_dts[i_flow]
#             cpn_time = (flow_dt - settle_dt) / gDaysInYear
#             cpn_flow = swap._fixedFlows[i_flow-1] / self._notional
#             cpn_times.append(cpn_time)
#             cpn_amounts.append(cpn_flow)

#         cpn_times = np.array(cpn_times)
#         cpn_amounts = np.array(cpn_amounts)

#         # Generate bond call times and prices
#         call_times = []
#         for dt in self._call_dts:
#             call_time = (dt - settle_dt) / gDaysInYear
#             call_times.append(call_time)
#         call_times = np.array(call_times)
#         call_prices = np.array(self._call_prices)

#         # Generate bond put times and prices
#         if self._swaptionType == IborSwaptionType.PAY:
#             call_price = 100.0
#             putPrice = 1e10
#         else:
#             call_price = 1e10
#             putPrice = 100.0

#         put_times = []
#         for put_dt in swap._adjusted_fixed_dts[1:]:
#             if put_dt <= self._exercise_dt:
#                 put_time = (put_dt - settle_dt) / gDaysInYear
#                 put_times.append(put_time)

#         put_times = np.array(put_times)
#         put_prices = np.array(self._put_prices)

#         maturity_dt = self._bond._maturity_dt
#         t_mat = (maturity_dt - settle_dt) / gDaysInYear
#         df_times = discount_curve._times
#         df_values = discount_curve._values

#         face = self._bond._face

#         if type(model) is HWTree:

#             """ We need to build the tree out to the bond maturity date. To be
#             more precise we only need to go out the the last option date but
#             we can do that refinement at a later date. """

#             model.buildTree(t_mat, df_times, df_values)
#             v1 = model.callableputtable_bond_Tree(cpn_times, cpn_amounts,
#                                                  call_times, call_prices,
#                                                  put_times, put_prices, face)
#             model._num_time_steps += 1
#             model.buildTree(t_mat, df_times, df_values)
#             v2 = model.callableputtable_bond_Tree(cpn_times, cpn_amounts,
#                                                  call_times, call_prices,
#                                                  put_times, put_prices, face)
#             model._num_time_steps -= 1

#             v_bondwithoption = (v1['bondwithoption'] + v2['bondwithoption'])/2
#             v_bondpure = (v1['bondpure'] + v2['bondpure'])/2

#             return {'bondwithoption': v_bondwithoption, 'bondpure': v_bondpure}

#         elif type(model) == BKTree:

#             """ Because we not have a closed form bond price we need to build
#             the tree out to the bond maturity which is after option expiry. """

#             model.buildTree(t_mat, df_times, df_values)
#             v1 = model.callableputtable_bond_Tree(cpn_times, cpn_amounts,
#                                                  call_times, call_prices,
#                                                  put_times, put_prices,
#                                                  face)
#             model._num_time_steps += 1
#             model.buildTree(t_mat, df_times, df_values)
#             v2 = model.callableputtable_bond_Tree(cpn_times, cpn_amounts,
#                                                  call_times, call_prices,
#                                                  put_times, put_prices,
#                                                  face)
#             model._num_time_steps -= 1

#             v_bondwithoption = (v1['bondwithoption'] + v2['bondwithoption'])/2
#             v_bondpure = (v1['bondpure'] + v2['bondpure'])/2

#             return {'bondwithoption': v_bondwithoption, 'bondpure': v_bondpure}
#         else:
#             raise FinError("Unknown model type")

# ###############################################################################

#     def __repr__(self):

#         s = label_to_string("MATURITY DATE", self._maturity_dt)
#         s += label_to_string("EXERCISE DATE", self._exercise_dt)
#         s += label_to_string("COUPON", self._cpn)
#         s += label_to_string("FREQUENCY", self._freq_type)
#         s += label_to_string("DAY COUNT TYPE", self._dc_type)
#         s += label_to_string("FACE AMOUNT", self._face)
#         s += label_to_string("CONVERSION RATIO", self._conversion_ratio)
#         s += label_to_string("START CONVERT DATE", self._start_convert_dt)

#         for i in range(0, len(self._call_dts)):
#             s += label_to_string("CALL DATE AND PRICE", self._call_dts[i],
#                                self._call_prices[i])

#         for i in range(0, len(self._put_dts)):
#             s += label_to_string("PUT DATE AND PRICE", self._put_dts[i],
#                                self._put_prices[i])

#         return s

# ###############################################################################

#     def print(self):
#         print(self)

# ###############################################################################
