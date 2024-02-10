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

from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Union,
    overload
)

import pandas as pd
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsTask
)
from qgis.PyQt.QtCore import (  # NULL,
    QObject,
    pyqtSignal
)

from .District import (
    BaseDistrict,
    District,
    Unassigned
)
from .Tasks import AggregateDistrictDataTask
from .utils import (
    gpd_read,
    makeFieldName
)

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class DistrictList(QObject):
    districtAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    districtRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    updating = pyqtSignal()
    updateComplete = pyqtSignal()
    updateTerminated = pyqtSignal()

    def __init__(self, plan: RedistrictingPlan, districts: List[BaseDistrict] = None):
        super().__init__(plan)
        self._plan = plan
        if not districts:
            self._index = pd.RangeIndex(plan.numDistricts + 1)
        else:
            self._index = pd.Index([d.district for d in districts])

        cols = self._keys = ['district', 'name', 'members',
                             self._plan.popField, 'deviation', 'pct_deviation']

        for field in self._plan.popFields:
            cols.append(field.fieldName)

        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                cols.append(fn)
            if field.pctbase and field.pctbase in cols:
                cols.append(f'pct_{fn}')

        cols += ['polsbyPopper', 'reock', 'convexHull']
        self._columns = pd.Index(cols)

        if districts:
            self._districts: Dict[int, BaseDistrict] = {}
            self.update({dist.district: dist for dist in districts})
        else:
            self._districts: Dict[int, BaseDistrict] = {
                0: Unassigned(self._plan)
            }

        self._needUpdate = False
        self._needGeomUpdate = False
        self._updateDistricts = None
        self._updateTask = None

    @overload
    def __getitem__(self, index: Union[str, int]) -> BaseDistrict:
        ...

    @overload
    def __getitem__(self, index: slice) -> List[BaseDistrict]:
        ...

    def __getitem__(self, index):
        if isinstance(index, slice):
            return DistrictList(self._plan, list(self._districts.values())[index])

        if isinstance(index, str):
            if index.isnumeric():
                index = int(index)
                if index in self._districts:
                    return self._districts[index]
                if 0 <= index <= self._plan.numDistricts:
                    return None
            else:
                d = next(iter(self._districts.values()), BaseDistrict(self._plan, 0))
                if hasattr(d, index):
                    return [getattr(dist, index) for dist in self.values() if dist.district != 0]
        elif isinstance(index, int):
            return list(self._districts.values())[index]

        raise IndexError()

    def __delitem__(self, index):
        if isinstance(index, District):
            index = index.district
        elif isinstance(index, str) and index.isnumeric():
            index = int(index)
        elif not isinstance(index, int):
            raise IndexError()

        if index in self._districts:
            i = list(self._districts.values()).index(self._districts[index])
            self.districtRemoved.emit(self._plan, self._districts[index], i)
            del self._districts[index]
        else:
            raise IndexError()

    def __iter__(self):
        return iter(self._districts.values())

    def __len__(self):
        return len(self._districts)

    def __contains__(self, index):
        if isinstance(index, BaseDistrict):
            return index.district in self._districts

        if isinstance(index, str) and index.isnumeric():
            index = int(index)

        return index in self._districts

    def __bool__(self) -> bool:
        return bool(self._districts)

    def _append(self, dist: District):
        self._districts[dist.district] = dist
        self._districts = {k: self._districts[k]
                           for k in sorted(self._districts)}
        i = list(self._districts.values()).index(dist)
        self.districtAdded.emit(self._plan, dist, i)

    def keys(self):
        return self._districts.keys()

    def values(self):
        return self._districts.values()

    def items(self):
        return self._districts.items()

    def index(self, district):
        return list(self._districts.values()).index(district)

    def update(self, districts: Dict[int, BaseDistrict]):
        self._districts.update(districts)
        self._districts = {k: self._districts[k]
                           for k in sorted(self._districts)}

    def clear(self):
        unassigned = self.unassigned
        self._districts.clear()
        self._districts[0] = unassigned

    @property
    def unassigned(self):
        return self._districts[0] if 0 in self._districts else None

    @property
    def updatingData(self):
        return self.updateDistricts() is not None

    def updateDistrictFields(self):
        for dist in self._districts.values():
            dist.updateFields()

    def addDistrict(self, district: int, name='', members=1, description='') -> District:
        dist = District(self._plan, district,
                        name, members, description)
        self._append(dist)
        return dist

    def deserializeDistrict(self, data):
        dist = District.deserialize(self._plan, data)
        if dist:
            self._append(dist)
        return dist

    def loadData(self, loadall=False):
        if self._plan.distLayer:
            geoPackagePath, _ = self._plan.distLayer.dataProvider().dataSourceUri().split('|')
            data = gpd_read(geoPackagePath, layer="districts")

            dists = list(range(self._plan.numDistricts+1)) if loadall \
                else self._districts

            for _, r in data.iterrows():
                if r['district'] in dists:
                    if not r["district"] in self._districts:
                        self.addDistrict(r['district'], r['name'], r['members'])
                    self._districts[r['district']].update(r)

    def updateData(self, data: pd.DataFrame, districts: List[int] = None):
        updateall = districts is None or districts == list(self._districts.keys())

        if districts is None:
            districts = range(0, self._plan.numDistricts+1)

        for d in districts:
            if updateall and not d in data.index and d in self._districts:
                self._districts[d].clear()
            elif d in data.index:
                if d in self._districts:
                    district = self._districts[d]
                else:
                    district = \
                        self.addDistrict(
                            int(d),
                            str(data.name[d]),
                            int(data.members[d])
                        ) if d > 0 \
                        else Unassigned(self._plan)
                district.update(data.loc[d])

    def updateTaskCompleted(self):
        self._plan.distLayer.reload()
        if self._updateTask.totalPop:
            self._plan.totalPopulation = self._updateTask.totalPop

        self.updateData(self._updateTask.districts, self._updateDistricts)
        self._plan.stats.update(None, self._updateTask.splits)

        if self._needGeomUpdate:
            self._plan.distLayer.triggerRepaint()

        self._needUpdate = False
        self._needGeomUpdate = False
        self._updateDistricts = None
        self._updateTask = None

        self.updateComplete.emit()

    def updateTaskTerminated(self):
        if self._updateTask.exception:
            self._plan.setError(
                f'{self._updateTask.exception!r}', Qgis.Critical)
        self._updateTask = None
        self._needUpdate = False
        self.updateTerminated.emit()

    def waitForUpdate(self):
        if self._updateTask:
            self._updateTask.waitForFinished()

    def updateDistricts(self, force=False) -> QgsTask:
        """ update aggregate district data from assignments, including geometry where requested

        :param force: Cancel any pending update and begin a new update
        :type force: bool

        :returns: QgsTask object representing the background update task
        :rtype: QgsTask
        """
        if not self._needUpdate and not force:
            return None

        if force:
            if self._updateTask:
                self._updateTask.cancel()
            self._updateTask = None

        if self._needUpdate and not self._updateTask:
            self._plan.clearErrors()

            self.updating.emit()
            self._updateTask = AggregateDistrictDataTask(
                self._plan,
                updateDistricts=self._updateDistricts,
                includeGeometry=self._needGeomUpdate,
                useBuffer=self._needGeomUpdate
            )
            self._updateTask.taskCompleted.connect(self.updateTaskCompleted)
            self._updateTask.taskTerminated.connect(self.updateTaskTerminated)
            QgsApplication.taskManager().addTask(self._updateTask)

        return self._updateTask

    def resetData(self, updateGeometry=False, districts: set[int] = None, immediate=False):
        if not self._plan.isValid():
            return

        if self._updateTask and updateGeometry and not self._needGeomUpdate:
            self._updateTask.cancel()
            self._updateTask = None
        self._needUpdate = True
        self._needGeomUpdate = self._needGeomUpdate or updateGeometry
        if districts:
            if not self._updateDistricts:
                self._updateDistricts = districts
            else:
                self._updateDistricts |= districts
        if immediate:
            self.updateDistricts(True)
