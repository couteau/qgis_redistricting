# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - class for calculating pending changes to
        a district

        begin                : 2022-05-25
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

from typing import (
    TYPE_CHECKING,
    Any,
    Dict
)

if TYPE_CHECKING:
    from .District import BaseDistrict
    from .Plan import RedistrictingPlan


class Delta:  # pylint: disable=too-few-public-methods
    def __init__(self, plan: RedistrictingPlan, district: BaseDistrict, delta: Dict[str, Any]):
        self._plan = plan
        self._district = district
        self._delta = delta

    def __getitem__(self, key):
        return self.__getattr__(key)

    def __getattr__(self, key: str):
        if key in ('name', 'district'):
            return getattr(self._district, key)

        if not self._delta:
            return None

        if key in self._delta:
            return self._delta[key]

        if key.endswith('deviation'):
            dev = self._district.deviation
            if dev is not None and self._plan.popField in self._delta:
                dev += self._delta[self._plan.popField]
                value = dev if key == 'deviation' \
                    else dev/self._district.ideal \
                    if self._district.ideal \
                    else None
            else:
                value = None
        else:
            if key.startswith(('new_', 'pct_')):
                attr = key[4:]
            else:
                raise AttributeError()

            if hasattr(self._district, attr):
                value = getattr(self._district, attr)
                if attr in self._delta:
                    value += self._delta[attr]

                if key.startswith('pct_'):
                    f = self._plan.dataFields[attr]
                    totalField = f.pctbase
                    if totalField and totalField in self._delta:
                        totalPop = getattr(self._district, totalField) + self._delta[totalField]
                        value = value/totalPop if totalPop else None
                    else:
                        value = None
            else:
                raise AttributeError()

        return value
