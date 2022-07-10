# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - plan-wide stats

         begin                : 2022-05-31
         git sha              : $Format:%H$
         copyright            : (C) 2022 by Cryptodira
         email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
***************************************************************************/
"""
from __future__ import annotations
from statistics import fmean
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanStats:
    def __init__(self, plan: RedistrictingPlan):
        self._plan = plan
        self._cutEdges = 0

    @property
    def avgReock(self):
        return fmean(self._plan.districts['reock'])

    @property
    def avgPolsbyPopper(self):
        return fmean(self._plan.districts['polsbyPopper'])

    @property
    def avgConvexHull(self):
        return fmean(self._plan.districts['convexHull'])

    @property
    def cutEdges(self):
        return self._cutEdges
