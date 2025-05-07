"""QGIS Redistricting Plugin - splits metric class

        begin                : 2025-05-03
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Cryptodira
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

from collections.abc import Iterable
from typing import TYPE_CHECKING

import pandas as pd

from ..utils import tr
from .base.lists import KeyedList
from .base.model import Factory
from .consts import DistrictColumns
from .metricslist import MetricLevel, MetricTriggers, RdsMetric, register_metrics
from .splits import RdsSplits

if TYPE_CHECKING:
    from .field import RdsGeoField
    from .plan import RdsPlan


class RdsSplitsMetric(
    RdsMetric[KeyedList[RdsSplits]],
    mname="splits",
    level=MetricLevel.GEOGRAPHIC,
    triggers=MetricTriggers.ON_UPDATE_GEOMETRY | MetricTriggers.ON_UPDATE_DEMOGRAPHICS,
):
    value = RdsMetric.value.factory(Factory(KeyedList[RdsSplits], with_owner=False), override=True)

    def __pre_init__(self):
        self.data: dict[str, pd.DataFrame] = {}

    def getSplitNames(self, field: "RdsGeoField", geoids: Iterable[str]):
        return {g: field.getName(g) for g in geoids}

    def calculate(self, populationData: pd.DataFrame, geometry, plan: "RdsPlan", **depends):
        def constant(s: pd.Series):
            array = s.to_numpy()
            return array.shape[0] == 0 or (array[0] == array).all()

        if plan is None:
            self._value: KeyedList[RdsSplits] = KeyedList[RdsSplits]()
            self.data: dict[str, pd.DataFrame] = {}
            return

        if populationData is not None:
            cols = [plan.distField]
            if DistrictColumns.POPULATION in populationData.columns:
                cols += (
                    [DistrictColumns.POPULATION]
                    + [f.fieldName for f in plan.popFields]
                    + [f.fieldName for f in plan.dataFields]
                )

            self.data = {}
            for field in plan.geoFields:
                g = populationData.dropna(subset=[field.fieldName])[[field.fieldName] + cols].groupby([field.fieldName])
                splits_data = g.filter(lambda x: not constant(x[plan.distField]))

                splitpop = splits_data[[field.fieldName] + cols].groupby([field.fieldName, plan.distField]).sum()

                if field.nameField and field.getRelation() is not None:
                    name_map = self.getSplitNames(field, splitpop.index.get_level_values(0).unique())
                    names = pd.Series(name_map.values(), index=name_map.keys(), name="__name", dtype=str)

                    splitpop = (
                        splitpop.reset_index(level=1)
                        .join(names)
                        .set_index("district", append=True)
                        .sort_values(by="__name")
                    )
                else:
                    splitpop = splitpop.sort_index()

                self.data[field.fieldName] = splitpop

    # pylint: disable=unsubscriptable-object,unsupported-assignment-operation
    def finished(self, plan: "RdsPlan"):
        new_splits: KeyedList[RdsSplits] = KeyedList[RdsSplits]()

        for f, split in self.data.items():
            if f not in self._value:
                new_splits[f] = RdsSplits(f, split)
                new_splits[f].caption = plan.geoFields[f].caption
                plan.geoFields[f].captionChanged.connect(new_splits[f].updateCaption)
            else:
                new_splits[f] = self._value[f]
                new_splits[f].setData(split)

        self._value = new_splits
        self.data: dict[str, pd.DataFrame] = {}

    def format(self, idx=None) -> str:
        if self._value is None:
            return None

        if idx is None:
            return repr({k: len(v) for k, v in self._value.items()})  # pylint: disable=no-member

        if idx not in self._value:
            return ""

        return f"{len(self._value[idx]):,}"

    def tooltip(self, idx=None):
        return tr("Double-click or press enter to see split details")


register_metrics([RdsSplitsMetric])
