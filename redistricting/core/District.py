# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - District classes

        begin                : 2022-01-15
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

from typing import Dict, Union, TYPE_CHECKING
from abc import abstractmethod
import pandas as pd
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.core import QgsFeature, QgsCategorizedSymbolRenderer

from .Field import DataField, BasePopulation
from .utils import makeFieldName, tr
from .Delta import Delta

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class BaseDistrict:  # pylint: disable=too-many-instance-attributes
    def __init__(self, plan: RedistrictingPlan, district: int, name='', description=''):
        self._plan = plan
        self._district = district
        self._name = name or str(district)
        self._description = description

        self._data = {}
        self._delta = None
        self.updateFields()
        self.clear()

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def baseField(self, fld: DataField):
        return self._plan.popField if fld.pctbase == BasePopulation.TOTALPOP \
            else self._plan.vapField if fld.pctbase == BasePopulation.VAP \
            else self._plan.cvapField if fld.pctbase == BasePopulation.CVAP \
            else None

    def getPctValue(self, fn: str):
        fld: DataField = self._plan.dataFields[fn]
        if not fld.pctbase:
            return None

        value = self._data[fn]
        if isinstance(value, (int, float)):
            baseField = self.baseField(fld)
            if baseField:
                total = getattr(self, baseField)
                return value / total if total else 0

        return None

    def __getattr__(self, key):
        if key[:4] == 'pct_' and key[4:] in self._data:
            return self.getPctValue(key[4:])

        if key in self._data:
            return self._data[key]

        raise AttributeError()

    def serialize(self):
        return {
            'district': self._district,
            'name': self._name,
            'description': self._description
        }

    @classmethod
    def deserialize(cls, plan, data: dict):
        if not 'district' in data:
            return None
        return cls(plan, **data)

    def updateFields(self):
        keys = {makeFieldName(field) for field in self._plan.dataFields}
        if self._plan.popField:
            keys.add(self._plan.popField)
        if self._plan.vapField:
            keys.add(self._plan.vapField)
        if self._plan.cvapField:
            keys.add(self._plan.cvapField)
        deletedKeys = set(self._data) - keys
        for k in deletedKeys:
            del self._data[k]

        added = {s: 0 for s in keys if not s in self._data}
        self._data.update(added)

    def clear(self):
        if self._plan.popField:
            self._data[self._plan.popField] = 0
        if self._plan.vapField:
            self._data[self._plan.vapField] = 0
        if self._plan.cvapField:
            self._data[self._plan.cvapField] = 0

        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            self._data[fn] = 0

        self.polsbyPopper = None
        self.reock = None
        self.convexHull = None

    @property
    def district(self):
        return self._district

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if value != self._name:
            oldValue = self._name
            self._name = value

            nindex = self._plan.distLayer.fields().indexFromName('name')
            if nindex != -1:
                features = self._plan.distLayer.getFeatures(
                    f"{self._plan.distField} = {self._district}")

                f: QgsFeature = next(features, None)
                if f is not None:
                    self._plan.distLayer.dataProvider().changeAttributeValues({
                        f.id(): {nindex: value}})
                    self._plan.distLayer.dataProvider().flushBuffer()
                    self._plan.distLayer.triggerRepaint()

            self._plan.planChanged.emit(
                self._plan, 'district.name', self._name, oldValue)

    @property
    def description(self):
        return self._description

    @property
    def population(self):
        return self._data.get(self._plan.popField) if self._plan.popField else 0

    @property
    def vap(self):
        return self._data.get(self._plan.vapField) if self._plan.vapField else 0

    @property
    def cvap(self):
        return self._data.get(self._plan.cvapField) if self._plan.cvapField else 0

    @property
    def delta(self):
        return self._delta

    @delta.setter
    def delta(self, value: Dict[str, int]):
        if value:
            self._delta = Delta(self._plan, self, value)
        else:
            self._delta = None

    @property
    @abstractmethod
    def ideal(self):
        ...

    @property
    @abstractmethod
    def deviation(self):
        ...

    @property
    @abstractmethod
    def pct_deviation(self):
        ...

    @property
    @abstractmethod
    def valid(self):
        ...

    @property
    def color(self):
        renderer = self._plan.distLayer.renderer()
        if isinstance(renderer, QgsCategorizedSymbolRenderer):
            idx = renderer.categoryIndexForValue(self._district)
            if idx != -1:
                cat = renderer.categories()[idx]
                return QColor(cat.symbol().color())

        return QColor(QPalette().color(QPalette.Normal, QPalette.Window))

    def update(self, data: Union[pd.Series, Dict[str, Union[int, float]]]):
        if self._plan.popField in data:
            self._data[self._plan.popField] = int(data[self._plan.popField] or 0)
        if self._plan.vapField and self._plan.vapField in data:
            self._data[self._plan.vapField] = int(data[self._plan.vapField] or 0)
        if self._plan.cvapField and self._plan.cvapField in data:
            self._data[self._plan.cvapField] = int(data[self._plan.cvapField] or 0)
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if fn in data:
                self._data[fn] = int(data[fn] or 0)

        # pylint: disable=attribute-defined-outside-init
        if 'polsbypopper' in data:
            self.polsbyPopper = data['polsbypopper']
        if 'reock' in data:
            self.reock = data['reock']
        if 'convexhull' in data:
            self.convexHull = data['convexhull']
        # pylint: enable=attribute-defined-outside-init


class Unassigned(BaseDistrict):
    def __init__(self, plan: RedistrictingPlan):
        super().__init__(
            plan,
            0,
            tr('Unassigned')
        )

    @property
    def ideal(self):
        return None

    @property
    def deviation(self):
        return None

    @property
    def pct_deviation(self):
        return None

    @property
    def valid(self):
        return None


class District(BaseDistrict):
    def __init__(self, plan: RedistrictingPlan, district: int, name='', members=1, description=''):
        super().__init__(plan, district, name, description)
        self._members = members

    def serialize(self):
        return super().serialize() | {'members': self._members}

    @property
    def members(self):
        return self._members

    @property
    def ideal(self):
        return self._members * self._plan.ideal

    @property
    def deviation(self):
        return self.population - self.ideal

    @property
    def pct_deviation(self):
        return self.deviation / self.ideal if self.ideal else None

    @property
    def valid(self):
        idealLower, idealUpper = self._plan.devBounds(self.members)
        return idealLower <= self.population <= idealUpper
