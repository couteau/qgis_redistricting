# -*- coding: utf-8 -*-
"""
/***************************************************************************
 RedistrictingPlan
        QGIS Redistricting Plugin - district manager
                              -------------------
        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

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

from typing import Dict, List, Union, TYPE_CHECKING, overload
import pandas as pd
from qgis.PyQt.QtCore import QObject, pyqtSignal, NULL
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsTask,
)
from .Utils import makeFieldName, tr
from .Tasks import AggregateDistrictDataTask
from .District import BaseDistrict, Unassigned, District

if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class DistrictList(QObject):
    districtAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    districtRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject', int)
    updating = pyqtSignal()
    updateComplete = pyqtSignal()
    updateTerminated = pyqtSignal()

    def __init__(self, plan: RedistrictingPlan):
        super().__init__(plan)
        self._plan = plan
        self._districts: Dict[int, BaseDistrict] = {
            0: Unassigned(self._plan)
        }
        self._keys = []
        self._headings = []
        self._needUpdate = False
        self._needGeomUpdate = False
        self._updateDistricts: set[int] = None
        self._updateTask = None
        self.updateColumnKeys()

    def updateField(self, fieldName, oldFieldName=None):
        for dist in self._districts.values():
            if oldFieldName and hasattr(dist, oldFieldName):
                delattr(dist, oldFieldName)
            setattr(dist, fieldName, 0)

    @overload
    def __getitem__(self, index: tuple) -> Union[str, int, float]:
        ...

    @overload
    def __getitem__(self, index: slice) -> List[BaseDistrict]:
        ...

    @overload
    def __getitem__(self, index: Union[int, str]) -> BaseDistrict:
        ...

    def __getitem__(self, index):
        if isinstance(index, slice):
            return list(self._districts.values())[index]

        self.update()
        if isinstance(index, tuple):
            row, col = index
            dist = list(self._districts.values())[row]
            if 0 <= col < len(self._keys):
                return getattr(dist, self._keys[col])
        elif isinstance(index, str):
            if index.isnumeric():
                index = int(index)
                if index in self._districts:
                    return self._districts[index]
                if 0 <= index <= self._plan.numDistricts:
                    return None
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
            self.districtRemoved.emit(self, self._districts[index], i)
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

    def _append(self, dist: District):
        self._districts[dist.district] = dist
        self._districts = {k: self._districts[k]
                           for k in sorted(self._districts)}
        i = list(self._districts.values()).index(dist)
        self.districtAdded.emit(self, dist, i)

    def keys(self):
        return self._districts.keys()

    def values(self):
        return self._districts.values()

    def items(self):
        return self._districts.items()

    def index(self, district):
        return list(self._districts.values()).index(district)

    @property
    def headings(self):
        return self._headings

    @property
    def columnKeys(self):
        return self._keys

    @property
    def updatingData(self):
        return self.update() is not None

    def waitForUpdate(self):
        if self._updateTask:
            self._updateTask.waitForFinished()

    def updateColumnKeys(self):
        self._keys = ['district', 'name',
                      self._plan.popField, 'deviation', 'pct_deviation']

        self._headings = [
            tr('District'),
            tr('Name'),
            tr('Population'),
            tr('Deviation'),
            tr('%Deviation')
        ]

        if self._plan.vapField:
            self._keys.append(self._plan.vapField)
            self._headings.append(tr('VAP'))

        if self._plan.cvapField:
            self._keys.append(self._plan.cvapField)
            self._headings.append(tr('CVAP'))
        for field in self._plan.dataFields:
            fn = makeFieldName(field)
            if field.sum:
                self._keys.append(fn)
                self._headings.append(field.caption)
            if field.pctbase:
                self._keys.append(f'pct_{fn}')
                self._headings.append(f'%{field.caption}')
        self._keys += ['polsbyPopper', 'reock', 'convexHull']
        self._headings += [
            tr('Polsby-Popper'),
            tr('Reock'),
            tr('Convex Hull'),
        ]

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
            dists = [str(d) for d in range(0, self._plan.numDistricts+1)] if loadall \
                else [str(d) for d in self._districts]
            # if len(dists) < self._plan.numDistricts:
            #    self._needUpdate = True

            features = self._plan.distLayer.getFeatures(
                f'{self._plan.distField} in ({",".join(dists)})')

            for f in features:
                if not f['district'] in self._districts:
                    self.addDistrict(f['district'])

                self._districts[f['district']].update(
                    {k: v if v != NULL else None for k, v in zip(
                        f.fields().names(), f.attributes())}
                )

    def updateData(self, data: pd.DataFrame, districts: List[int]):
        if districts is None:
            districts = range(0, self._plan.numDistricts+1)
        for d in districts:
            if not d in data.index and d in self._districts:
                self._districts[d].clear()
            elif d in data.index:
                if d in self._districts:
                    district = self._districts[d]
                else:
                    district = self.addDistrict(
                        d) if d > 0 else Unassigned(self._plan)
                district.update(data.loc[d])

    def update(self, force=False) -> QgsTask:
        """ update aggregate district data from assignments, including geometry where requested

        :param force: Cancel any pending update and begin a new update
        :type force: bool

        :returns: QgsTask object representing the background update task
        :rtype: QgsTask
        """
        def taskCompleted():
            self._plan.distLayer.reload()
            if self._updateTask.totalPop:
                self._plan.totalPopulation = self._updateTask.totalPop

            self.updateData(self._updateTask.districts, self._updateDistricts)

            if self._needGeomUpdate:
                self._plan.distLayer.triggerRepaint()
                self._plan._cutEdges = len(  # pylint: disable=protected-access
                    self._updateTask.cutEdges)

            self._needUpdate = False
            self._needGeomUpdate = False
            self._updateDistricts = None
            self._updateTask = None

            self.updateComplete.emit()

        def taskTerminated():
            if self._updateTask.exception:
                self._plan.setError(
                    f'{self._updateTask.exception!r}', Qgis.Critical)
            self._updateTask = None
            self.updateTerminated.emit()

        self._plan.clearError()

        if self._updateTask and force:
            self._updateTask.cancel()
            self._updateTask = None

        if self._needUpdate and not self._updateTask:
            self.updating.emit()
            self._updateTask = AggregateDistrictDataTask(
                self._plan,
                districts=self._updateDistricts,
                includeGeometry=self._needGeomUpdate,
                useBuffer=self._needGeomUpdate
            )
            self._updateTask.taskCompleted.connect(taskCompleted)
            self._updateTask.taskTerminated.connect(taskTerminated)
            QgsApplication.taskManager().addTask(self._updateTask)

        return self._updateTask

    def resetData(self, updateGeometry=False, districts: set[int] = None, immediate=False):
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
            self.update(True)
