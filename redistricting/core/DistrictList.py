# -*- coding: utf-8 -*-
"""District manager

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

from math import (
    ceil,
    floor
)
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Optional,
    Union,
    overload
)

import numpy as np
import pandas as pd
from qgis.core import (
    QgsFeature,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)

from .District import District
from .layer import LayerReader
from .utils import (
    connect_layer,
    makeFieldName,
    tr
)

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan

IntTypes = (QVariant.Int, QVariant.UInt, QVariant.LongLong, QVariant.ULongLong)


class DistrictAccessor:
    def __init__(self, dl: DistrictList):
        self._list = dl

    def __getitem__(self, i: int) -> District:
        if i not in self._list._index:
            raise IndexError()

        if i not in self._list._districts:
            self._list._districts[i] = District(i, self._list)
        return self._list._districts[i]


class DistrictList(QObject):
    districtChanged = pyqtSignal('PyQt_PyObject')

    def __init__(self, plan: RedistrictingPlan, data: Optional[pd.DataFrame] = None):
        super().__init__(plan)
        self._plan = plan
        self._districts = {}
        self._accessor = DistrictAccessor(self)
        if data is None:
            self._index = pd.RangeIndex(plan.numDistricts + 1)
            self._data = pd.DataFrame(index=self._index)
        else:
            self._index = data.index
            self._data = data
        self._columns = self._data.columns

        self._totalPopulation = 0
        self.updateDistrictFields()

    @overload
    def __getitem__(self, index: Union[str, int]) -> District:
        ...

    @overload
    def __getitem__(self, index: slice) -> DistrictList:
        ...

    @overload
    def __getitem__(self, index: tuple) -> Any:
        ...

    def __getitem__(self, index):
        district = None
        field = None

        if isinstance(index, tuple):
            index, field = index
            if isinstance(field, int) and isinstance(index, int):
                return self._data.iat[index, field+1]

        if isinstance(index, slice):
            if field:
                if isinstance(field, int):
                    acc = self._data.loc
                else:
                    acc = self._data.iloc
                return list(acc[index, field])

            return DistrictList(self._plan, self._data.loc[index])

        if isinstance(index, str):
            if index.isnumeric():
                if int(index) in self._index:
                    district = self.district[int(index)]
            elif index in self._data.columns:
                return list(self._data[index])
            else:
                i = self._data.loc[self._data["name"] == index]
                if len(i) == 1:
                    district = self.district[i.index[0]]
        elif isinstance(index, int):
            district = self.district[self._index[index]]

        if district:
            if field:
                return district[field]
            return district

        raise IndexError()

    def __iter__(self):
        return (self._accessor[d] for d in self._index)

    def __len__(self):
        return len(self._index)

    def __contains__(self, index):
        if isinstance(index, District):
            return index.district in self._index

        if isinstance(index, str) and index.isnumeric():
            index = int(index)

        return index in self._data.index

    def __bool__(self) -> bool:
        return not self._data.empty

    def keys(self):
        return list(self._data.index)

    def values(self):
        return (self._accessor[d] for d in self._data.index)

    def items(self):
        return ((d, self._accessor[d]) for d in range(len(self._data)))

    def index(self, district: District):
        return district.district

    def clear(self):
        cols = [self.popField]

        for field in self._plan.popFields:
            cols.append(field.fieldName)

        for field in self._plan.dataFields:
            if field.sum:
                cols.append(makeFieldName(field))

        s = self._data[cols].sum()

        cols = self._data.columns
        self._data = pd.DataFrame(index=self._index, columns=cols)
        self._data.loc[0].update(s)

    @property
    def layer(self) -> QgsVectorLayer:
        return self._plan.distLayer

    @property
    def popField(self):
        return self._plan.popField

    @property
    def district(self):
        return self._accessor

    @property
    def headings(self):
        return self._headings

    @property
    def columns(self):
        return self._columns

    @property
    def ideal(self):
        return round(self._totalPopulation / self._plan.numSeats)

    def idealRange(self, members: int = 1):
        maxDeviation = int(self._totalPopulation *
                           self._plan.deviation / self._plan.numDistricts)
        idealUpper = ceil(members * self._totalPopulation / self._plan.numSeats) + maxDeviation
        idealLower = floor(self._totalPopulation / self._plan.numSeats) - maxDeviation
        return (idealLower, idealUpper)

    def getAssignments(self, district: int = None):
        s = LayerReader(self._plan.assignLayer)
        if district is not None:
            filt = {self._plan.distField: district}
        else:
            filt = None
        return s.read_layer(['fid', self._plan.geoIdField, self._plan.distField], order='fid', filt=filt, read_geometry=False)

    def updateNumDistricts(self):
        if self._plan.numDistricts != len(self._data):
            self._index = pd.RangeIndex(self._plan.numDistricts + 1)
            self.createDataFrame(self._index, self._columns, self._data)

    def createDataFrame(self, districts, columns: dict[str, pd.Series], data: pd.DataFrame = None):
        self._data = pd.DataFrame(
            {"fid": pd.Series(pd.NA, index=self._index, dtype="Int64")} |
            columns |
            {"description": pd.Series("", index=self._index)},
            index=districts
        )
        self._data.loc[0, ["name", "members", "polsbypopper", "reock", "convexhull"]] = \
            (tr("Unassigned"), None, None, None, None)
        self._columns = list(columns.keys())
        if data is not None:
            self.setData(data)

    def updateDistrictFields(self):
        if self._plan.popField is None:
            cols = {
                'district': pd.Series(self._index, index=self._index, dtype="Int64"),
                'name': pd.Series("", index=self._index, dtype=str),
                'members': pd.Series(1, index=self._index, dtype="Int64"),
                'deviation': pd.Series(pd.NA, index=self._index, dtype="Int64"),
                'pct_deviation': pd.Series(pd.NA, index=self._index, dtype="Float64"),
            }
            self._headings = [
                tr('District'),
                tr('Name'),
                tr('Members'),
                tr('Deviation'),
                tr('%Deviation')
            ]
        else:
            cols = {
                'district': pd.Series(self._index, index=self._index, dtype="Int64"),
                'name': pd.Series("", index=self._index, dtype=str),
                'members': pd.Series(1, index=self._index, dtype="Int64"),
                self.popField: pd.Series(0, index=self._index, dtype="Int64"),
                'deviation': pd.Series(pd.NA, index=self._index, dtype="Int64"),
                'pct_deviation': pd.Series(pd.NA, index=self._index, dtype="Float64"),
            }
            self._headings = [
                tr('District'),
                tr('Name'),
                tr('Members'),
                tr('Population'),
                tr('Deviation'),
                tr('%Deviation')
            ]

        for field in self._plan.popFields:
            cols[field.fieldName] = pd.Series(
                0,
                index=self._index,
                dtype="Int64" if field.fieldType() in IntTypes else "Float64"
            )
            self._headings.append(field.caption)

        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                cols[fn] = pd.Series(
                    0,
                    index=self._index,
                    dtype="Int64" if field.fieldType() in IntTypes else "Float64"
                )
                self._headings.append(field.caption)
            if field.pctbase and field.pctbase in cols:
                cols[f"pct_{fn}"] = pd.Series(0, index=self._index, dtype="Float64")
                self._headings.append(f"%{field.caption}")

        cols |= {
            'polsbypopper': pd.Series(pd.NA, index=self._index, dtype="Float64"),
            'reock': pd.Series(pd.NA, index=self._index, dtype="Float64"),
            'convexhull': pd.Series(pd.NA, index=self._index, dtype="Float64")
        }
        self._headings += [
            tr('Polsby-Popper'),
            tr('Reock'),
            tr('Convex Hull'),
        ]
        savecols = [col for col in self._data.columns if col in cols or col in {"fid", "description"}]
        data = self._data[savecols].copy()
        self.createDataFrame(self._index, cols, data)

    def setData(self, data: pd.DataFrame):
        dtypes = {c: self._data[c].dtype for c in data.columns if c in self._data.columns}
        self._data.update(data.astype(dtype=dtypes, copy=False))
        # self._data = self._data.astype(dtype=dtypes, copy=False)
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.pctbase and field.pctbase in self._data.columns:
                self._data[f'pct_{fn}'] = self._data[fn].div(self._data[field.pctbase], fill_value=0)

    def loadData(self):
        if not self._plan.isValid():
            return

        if self._plan.distLayer:
            with connect_layer(self._plan.distLayer) as db:
                data = pd.read_sql(
                    "select * from districts",
                    db,
                    columns=self._data.columns
                )

            self.setData(data.set_index("district", drop=False).replace({np.nan: None}))
            self._totalPopulation = int(self._data[self.popField].sum())

            if self._data.loc[1:, "deviation"].isna().any():
                self._data.loc[1:, "deviation"] = \
                    self._data.loc[1:, self.popField].sub(self._data.loc[1:, "members"] * self.ideal)
                self._data.loc[1:, "pct_deviation"] = \
                    self._data.loc[1:, "deviation"].div(self._data.loc[1:, "members"] * self.ideal)

            if self._data.loc[1:, "name"].isna().any():
                self._data.loc[1:, "name"] = tr("District") + " " + self._data.loc[1: "district"].astype(str)

    READONLY_FIELDS = {"fid", "district"}

    def saveData(self, district=None):
        def changeAttributes(dist: int, feature: QgsFeature):
            values = {}
            for idx, field in field_map.items():
                if field in self._data.columns and field not in self.READONLY_FIELDS:
                    value = self._data.at[dist, field]
                    if value != feature[idx]:
                        values[idx] = value
            if values:
                self._plan.distLayer.changeAttributeValues(feature.id(), values)

        fields = self._plan.distLayer.fields()
        field_map = dict(map(lambda i, j: (i, j), fields.allAttributesList(), fields.names()))
        dist_idx = fields.indexFromName(self._plan.distField)
        if district is None:
            fids = self._data["fid"].dropna()
            self._plan.distLayer.startEditing()
            for feat in self._plan.distLayer.getFeatures(list(fids)):
                changeAttributes(feat[dist_idx], feat)
            self._plan.distLayer.commitChanges(True)
        else:
            fid = int(self._data.at[district, "fid"])
            if pd.isna(fid):
                raise ValueError("Invalid fid for district")

            feat = self._plan.distLayer.getFeature(fid)
            if feat is None:
                raise ValueError("Invalid fid for district")

            self._plan.distLayer.startEditing()
            changeAttributes(district, feat)
            self._plan.distLayer.commitChanges(True)

    def changeDistrictAttribute(self, district: int, attr: str, value: Any):
        self._data.at[district, attr] = value
        self.saveData(district)
        self.districtChanged.emit(self.district[district])

    # stats
    def _avgScore(self, score: str):
        return self._data.loc[1:, score].mean()

    @property
    def avgPolsbyPopper(self):
        return self._avgScore("polsbypopper")

    @property
    def avgReock(self):
        return self._avgScore("reock")

    @property
    def avgConvexHull(self):
        return self._avgScore("convexhull")

    def getSelectionData(self, selection: Iterable[tuple[int, int]]) -> pd.DataFrame:
        if selection is not None:
            # create a dataframe of bools with the same dimensions as data
            s = (self._data.iloc[:, 1:-1] != self._data.iloc[:, 1:-1]).fillna(False)
            # set elements to True if in selection
            for row, col in selection:
                s.iloc[row, col] = True
            # select the elements of data that are contained in selection
            df = self._data[s]
            # drop the unselected rows and columns
            df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
        else:
            df = self._data.iloc[:, 1:-1]
        df = df.fillna('')
        df.columns.name = tr("District")
        return df

    def getAsHtml(self, selection: Iterable[tuple[int, int]]) -> str:
        return self.getSelectionData(selection).style.to_html()

    def getAsCsv(self, selection: Iterable[tuple[int, int]]) -> str:
        return self.getSelectionData(selection).to_csv()
