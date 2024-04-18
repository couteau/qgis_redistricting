# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - plan-wide stats

         begin                : 2024-03-10
         git sha              : $Format:%H$
         copyright            : (C) 2024 by Cryptodira
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
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Iterator,
    Optional,
    Union
)

import pandas as pd
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .Field import GeoField
from .PlanSplits import Splits

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class SplitsList:
    class HeadingAccessor:
        def __init__(self, plan: "RedistrictingPlan"):
            self._plan = plan

        def __getitem__(self, key: Union[int, str]):
            return self._plan.geoFields[key].caption

        def __len__(self) -> int:
            return len(self._plan.geoFields)

    def __init__(self, plan: "RedistrictingPlan"):
        self._plan = plan
        self._splits = None
        self.initSplits()

    def __contains__(self, key: str) -> bool:
        return key in self._splits

    def __getitem__(self, key: Union[str, int, GeoField]) -> Splits:
        if isinstance(key, GeoField):
            key = key.fieldName
        elif isinstance(key, int):
            key = self._plan.geoFields[key].fieldName

        return self._splits[key]

    def __setitem__(self, key: Union[str, int, GeoField], value: Splits):
        if isinstance(key, GeoField):
            key = key.fieldName
        elif isinstance(key, int):
            key = self._plan.geoFields[key].fieldName

        self._splits[key] = value

    def __delitem__(self, key: Union[str, int, GeoField]):
        if isinstance(key, GeoField):
            key = key.fieldName
        elif isinstance(key, int):
            key = self._plan.geoFields[key].fieldName

        del self._splits[key]

    def __len__(self) -> int:
        return len(self._splits)

    def __iter__(self) -> Iterator[Splits]:
        return self._splits.__iter__()

    def __eq__(self, other: "SplitsList"):
        return self._splits == other._splits

    def __ne__(self, other: "SplitsList"):
        return self._splits != other._splits

    def keys(self) -> Iterable[str]:
        return self._splits.keys()

    def values(self) -> Iterable[Splits]:
        return self._splits.values()

    def items(self) -> Iterable[tuple[str, Splits]]:
        return self._splits.items()

    def index(self, item: Splits) -> str:
        return item.field.fieldName

    def count(self, item: Splits) -> int:
        return 1 if item.field.fieldName in self._splits else 0

    def get(self, key: str, default: Optional[Splits] = None):
        return self._splits.get(key, default)

    @property
    def headings(self):
        return self.HeadingAccessor(self._plan)

    def initSplits(self):
        oldSplits = self._splits
        self._splits: dict[str, Splits] = {
            f.fieldName: Splits(self._plan, f) for f in self._plan.geoFields
        }
        if oldSplits is not None:
            for f, s in oldSplits.items():
                if f in self._splits:
                    self._splits[f].setData(s.data)


class PlanStats(QObject):
    statsUpdating = pyqtSignal()
    statsUpdated = pyqtSignal()

    def __init__(self, plan: "RedistrictingPlan", parent: Optional[QObject] = None):
        super().__init__(parent)
        self._plan = plan
        self._cutEdges = None
        self._splits = SplitsList(plan)

    def serialize(self):
        data = {
            'cut-edges': self._cutEdges,
            'plan-splits': {f: s.serialize() for f, s in self._splits.items()}
        }
        # remove nulls
        data = {k: v for k, v in data.items() if v is not None}
        return data

    @classmethod
    def deserialize(cls, data: dict[str, Any], plan: "RedistrictingPlan"):
        instance = cls(plan)
        instance._cutEdges = data.get('cut-edges')
        for f, s in data.get('plan-splits', {}).items():
            instance._splits[f] = Splits.deserialize(plan, plan.geoFields[f], s)
        return instance

    @property
    def cutEdges(self):
        return self._cutEdges

    @property
    def splits(self) -> SplitsList:
        return self._splits

    @property
    def totalPopulation(self):
        return self._plan.totalPopulation

    # stats
    def _avgScore(self, score: str) -> Union[float, None]:
        values = self._plan.districts[1:, score]
        count = len(values)
        if count == 0:
            return None

        return sum(values) / count

    @ property
    def avgPolsbyPopper(self):
        return self._avgScore("polsbypopper")

    @ property
    def avgReock(self):
        return self._avgScore("reock")

    @ property
    def avgConvexHull(self):
        return self._avgScore("convexhull")

    def updateGeoFields(self):
        self.statsUpdating.emit()
        self._splits.initSplits()
        self.statsUpdated.emit()

    def setData(self, cutEdges, splits: dict[str, pd.DataFrame]):
        self.statsUpdating.emit()
        if cutEdges is not None:
            self._cutEdges = cutEdges

        if splits is not None:
            for f, split in splits.items():
                field = self._plan.geoFields[f]
                if field is not None:
                    if f not in self._splits:
                        self._splits[f] = Splits(self._plan, field, self)

                    self._splits[f].setData(split)
        self.statsUpdated.emit()
