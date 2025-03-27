# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to calculate pending changes

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
from typing import (
    TYPE_CHECKING,
    Optional
)

import pandas as pd

from ... import CanceledError
from ...models import DistrictColumns
from ...utils import tr
from ._debug import debug_thread
from .updatebase import AggregateDataTask

if TYPE_CHECKING:
    from ...models import RdsPlan


class AggregatePendingChangesTask(AggregateDataTask):
    def __init__(
        self,
        plan: "RdsPlan",
        popData: Optional[pd.DataFrame] = None,
        assignments: Optional[pd.DataFrame] = None
    ):
        super().__init__(plan, tr('Computing pending changes'))
        self.data = None
        self.popData = popData
        self.assignments = assignments

    def run(self):
        def checkCanceled():
            if self.isCanceled():
                raise CanceledError()

        debug_thread()

        try:
            if self.assignments is None:
                with self._connectSqlOgrSqlite(self.assignLayer.dataProvider()) as db:
                    self.assignments: pd.DataFrame = pd.read_sql(
                        f"SELECT fid, {self.geoIdField}, {self.distField} as old_{self.distField} FROM assignments",
                        db,
                        index_col="fid"
                    )
                checkCanceled()

            if self.popData is None:
                self.popData = self.loadPopData()
                checkCanceled()

            dindex = self.assignLayer.fields().lookupField(self.distField)
            if dindex == -1:
                return False
            gindex = self.assignLayer.fields().lookupField(self.geoIdField)
            if gindex == -1:
                return False

            index = []
            data = []
            for k, v in self.assignLayer.editBuffer().changedAttributeValues().items():
                if dindex in v:
                    index.append(k)
                    data.append(v[dindex])
            df_new = pd.DataFrame({f"new_{self.distField}": data}, index=index)

            checkCanceled()

            pending = self.assignments.loc[index].join(df_new)
            pending = pending[pending[f'new_{self.distField}'] != pending[f'old_{self.distField}']]
            if len(pending) == 0:
                return True

            pending = pending.join(self.popData, on=self.geoIdField, how="inner")

            newdist = pending\
                .drop(columns=f"old_{self.distField}")\
                .groupby(f'new_{self.distField}')\
                .sum(numeric_only=True)
            checkCanceled()
            olddist = pending\
                .drop(columns=f"new_{self.distField}")\
                .groupby(f'old_{self.distField}')\
                .sum(numeric_only=True)
            checkCanceled()

            data = newdist.sub(olddist, fill_value=0)
            dist = self.assignments\
                .join(self.popData, on=self.geoIdField)\
                .drop(columns=self.geoIdField)\
                .groupby(f"old_{self.distField}")\
                .sum()
            checkCanceled()
            dist = dist.loc[dist.index.intersection(data.index)]

            new = pd.DataFrame(0, index=data.index.difference(dist.index), columns=dist.columns)
            if len(new) > 0:
                dist = pd.concat([dist, new])
            members = [self.districts[f"{d:04}"].members for d in dist.index]
            dist["members"] = members

            data[f"new_{DistrictColumns.POPULATION}"] = dist[DistrictColumns.POPULATION] + \
                data[DistrictColumns.POPULATION]
            data["deviation"] = data[f"new_{DistrictColumns.POPULATION}"] - (dist["members"] * self.ideal)
            data["pct_deviation"] = data["deviation"] / (dist["members"] * self.ideal)
            for f in self.popFields:
                data[f"new_{f.fieldName}"] = dist[f.fieldName] + data[f.fieldName]
            for f in self.dataFields:
                data[f"new_{f.fieldName}"] = dist[f.fieldName] + data[f.fieldName]
                pctbase = DistrictColumns.POPULATION if f.pctBase == self.popField else f.pctBase
                if pctbase:
                    data[f"pct_{f.fieldName}"] = data[f"new_{f.fieldName}"] / data[f"new_{pctbase}"]

            checkCanceled()

            data["__name"] = pd.Series([self.plan.districts[str(i).rjust(4, "0")].name for i in data.index], data.index)

            cols = [f"new_{DistrictColumns.POPULATION}", DistrictColumns.POPULATION, "deviation", "pct_deviation"]
            for f in self.popFields:
                cols.append(f"new_{f.fieldName}")
                cols.append(f.fieldName)
            for f in self.dataFields:
                cols.append(f"new_{f.fieldName}")
                cols.append(f.fieldName)
                if f.pctBase:
                    cols.append(f"pct_{f.fieldName}")

            self.data = data.set_index("__name")[cols]
            checkCanceled()
        except CanceledError:
            self.data = None
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True
