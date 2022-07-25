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
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 *   This program is distributed in the hope that it will be useful, but   *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the          *
 *   GNU General Public License for more details. You should have          *
 *   received a copy of the GNU General Public License along with this     *
 *   program. If not, see <http://www.gnu.org/licenses/>.                  *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations
from statistics import fmean
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan
    from .Field import Field


class PlanStats:
    def __init__(self, plan: RedistrictingPlan):
        self._plan = plan
        self._cutEdges = 0
        self.updateSplits()
        self._plan.planChanged.connect(self.updateSplits)

    def planChanged(self, plan, field, oldValue, newValue):  # pylint: disable=unused-argument
        if field == 'geo-fields':
            self.updateSplits()

    def updateSplits(self):
        self._splits: Dict[Field, int] = {
            f: [] for f in self._plan.geoFields
        }

    def serialize(self):
        return {
            'cut-edges': self._cutEdges,
            'splits': {
                f.fieldName: split for f, split in self._splits.items()
            }
        }

    @classmethod
    def deserialize(cls, plan: RedistrictingPlan, data: Dict[str, Any]):
        stats = cls(plan)
        stats._cutEdges = data.get('cut-edges', 0)
        for f, split in data.get('splits', {}).items():
            field = plan.geoFields[f]
            if field is not None:
                stats._splits[field] = split
        return stats

    @property
    def avgReock(self):
        if len(self._plan.districts) <= 1:
            return None

        values = self._plan.districts[1:]['reock']
        if None in values:
            return None

        return fmean(values)

    @property
    def avgPolsbyPopper(self):
        if len(self._plan.districts) <= 1:
            return None

        values = self._plan.districts[1:]['polsbyPopper']
        if None in values:
            return None

        return fmean(values)

    @property
    def avgConvexHull(self):
        if len(self._plan.districts) <= 1:
            return None

        values = self._plan.districts[1:]['convexHull']
        if None in values:
            return None

        return fmean(values)

    @property
    def cutEdges(self):
        return self._cutEdges

    @property
    def splits(self) -> Dict[Field, int]:
        return self._splits

    def update(self, cutEdges, splits):
        self._cutEdges = cutEdges
        for f, split in splits.items():
            field = self._plan.geoFields[f]
            if field is not None:
                self._splits[field] = split
