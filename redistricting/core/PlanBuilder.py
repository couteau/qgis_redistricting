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
from copy import deepcopy
import pathlib
from typing import Union
from uuid import uuid4
from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from .utils import tr
from .Tasks import CreatePlanLayersTask
from .BasePlanBuilder import BasePlanBuilder
from .PlanImport import PlanImporter
from .Plan import RedistrictingPlan


class PlanBuilder(BasePlanBuilder):
    progressChanged = pyqtSignal(int)
    layersCreated = pyqtSignal('PyQt_PyObject')

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._importer: PlanImporter = None
        self._createLayersTask = None

    @classmethod
    def fromPlan(cls, plan: RedistrictingPlan, parent: QObject = None):
        # using deepcopy forces duplication of the data and geo fields
        newplan = deepcopy(plan)
        instance = super().fromPlan(newplan, parent)
        instance._plan = None  # pylint: disable=protected-access
        return instance

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._createLayersTask:
            self._createLayersTask.cancel()

    def setPlanImporter(self, value: PlanImporter):
        self._importer = value
        return self

    def setGeoPackagePath(self, value: Union[str, pathlib.Path]):
        if isinstance(value, str):
            value = pathlib.Path(value)
        elif not isinstance(value, pathlib.Path):
            raise ValueError(tr('Invalid GeoPackage path'))

        if value.resolve().exists():
            self.pushError(tr('GeoPackage already exists at location {path}').format(path=value))

        self._geoPackagePath = value
        return self

    def createLayers(self, plan: RedistrictingPlan):
        def taskCompleted():
            plan._totalPopulation = self._createLayersTask.totalPop  # pylint: disable=protected-access
            self._createLayersTask = None
            plan.addLayersFromGeoPackage(self._geoPackagePath)
            if self._importer:
                self._importer.importPlan(plan)
            else:
                plan.resetData(updateGeometry=True)
            self.layersCreated.emit(plan)

        def taskTerminated():
            if self._createLayersTask.isCanceled():
                self.setError(tr('Create layers canceled'), Qgis.UserCanceled)
            elif self._createLayersTask.exception:
                self.pushError(
                    tr('Error creating new {} layer: {}').format(
                        tr('assignment'), self._createLayersTask.exception),
                    Qgis.Critical
                )
            self._createLayersTask = None

        if not plan:
            return None

        self._createLayersTask = CreatePlanLayersTask(
            plan,
            str(self._geoPackagePath),
            self._sourceLayer,
            self._sourceIdField)
        self._createLayersTask.taskCompleted.connect(taskCompleted)
        self._createLayersTask.taskTerminated.connect(taskTerminated)
        self._createLayersTask.progressChanged.connect(self.setProgress)

        QgsApplication.taskManager().addTask(self._createLayersTask)

        return self._createLayersTask

    def createPlan(self, parent: QObject = None, createLayers=True):
        self.clearErrors()

        if createLayers:
            if not self._geoPackagePath:
                self.pushError(
                    tr('GeoPackage path must be specified to create plan layers'),
                    Qgis.Critical
                )
                return None

            try:
                self._geoPackagePath.touch()
            except FileExistsError:
                self.pushError(
                    tr('GeoPackage {path} already exists').format(path=self._geoPackagePath),
                    Qgis.Critical
                )
                return None
            except PermissionError:
                self.pushError(
                    tr('Cannot create GeoPackage at {path}: insufficient permissions').format(
                        path=self._geoPackagePath),
                    Qgis.Critical
                )
                return None
            except OSError as e:
                self.pushError(
                    tr('Cannot create GeoPackage at {path}: {error}')
                    .format(path=self._geoPackagePath, error=e),
                    Qgis.Critical
                )
                return None

        if not self.validate():
            return None

        data = {
            'id': str(uuid4()),
            'name': self._name,
            'description': self._description,
            'num-districts': self._numDistricts,
            'num-seats': self._numSeats if self._numSeats > self._numDistricts else None,
            'deviation': self._deviation,
            'geo-id-field': self._geoIdField,
            'geo-id-display': self._geoDisplay,
            'dist-field': self._distField,
            'pop-layer': self._popLayer.id(),
            'join-field': self._joinField if self._joinField != self._geoIdField else None,
            'pop-field': self._popField,
            'vap-field': self._vapField,
            'cvap-field': self._cvapField,
            'src-layer': self._sourceLayer.id() if self._sourceLayer != self._popLayer else None,
            'src-id-field': self._sourceIdField if self._sourceIdField != self._geoIdField else None,
            'data-fields': [field.serialize() for field in self._dataFields],
            'geo-fields': [field.serialize() for field in self._geoFields],
        }

        plan = RedistrictingPlan.deserialize({k: v for k, v in data.items() if v is not None}, parent)
        if createLayers:
            self.createLayers(plan)

        return plan