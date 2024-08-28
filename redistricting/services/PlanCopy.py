# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - copy plans

        begin                : 2022-06-01
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

import pathlib
import shutil
import sqlite3
from contextlib import closing
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    Union
)

from qgis.core import Qgis
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)
from qgis.utils import spatialite_connect

from ..models import RdsSplits
from ..utils import tr
from .DistrictIO import DistrictReader
from .ErrorList import ErrorListMixin
from .PlanBuilder import PlanBuilder

if TYPE_CHECKING:
    from ..models.Plan import RdsPlan


class PlanCopier(ErrorListMixin, QObject):
    progressChanged = pyqtSignal(int)
    copyComplete = pyqtSignal('PyQt_PyObject')

    def __init__(
        self,
        sourcePlan: RdsPlan
    ):
        super().__init__(sourcePlan)
        self._plan = sourcePlan
        self._builder: PlanBuilder = None

    def cancel(self):
        if self._builder:
            self._builder.cancel()

    def copyPlan(
        self,
        planName: str,
        description: str,
        destGpkgPath: Union[str, pathlib.Path],
        copyAssignments: bool = True,
        parent: Optional[QObject] = None
    ):
        def planCreated(plan):
            self.copyComplete.emit(plan)

        if not destGpkgPath:
            raise ValueError(tr('Destination GeoPackage path required'))

        self.clearErrors()

        self._builder = PlanBuilder.fromPlan(self._plan)
        self._builder.setName(planName)
        self._builder.setDescription(description)

        # if not copying assignments, emit the copyComplete signal
        # only after plan layers are created
        if not copyAssignments:
            self._builder.setGeoPackagePath(destGpkgPath)
            self._builder.layersCreated.connect(planCreated)
            self._builder.progressChanged.connect(self.progressChanged)

        plan = self._builder.createPlan(not copyAssignments, planParent=parent)
        if not plan:
            self._errors = self._builder.errors()
            return None

        if copyAssignments:
            shutil.copyfile(self._plan.geoPackagePath, destGpkgPath)
            plan.addLayersFromGeoPackage(destGpkgPath)

            for f in plan.geoFields:
                split = RdsSplits(plan, f, plan.metrics)
                split.setData(self._plan.metrics.splits[f.fieldName].data.copy())
                plan.metrics.splits[f.fieldName] = split

            reader = DistrictReader(
                plan.distLayer,
                distField=plan.distField,
                popField=plan.popField,
                columns=plan.districtColumns
            )
            reader.loadDistricts(plan)

            planCreated(plan)

        return plan

    def copyBufferedAssignments(self, target: RdsPlan):
        if not self._plan.assignLayer.isEditable():
            return

        buffer = self._plan.assignLayer.editBuffer()
        values: dict[int, dict[int, Any]] = buffer.changedAttributeValues()
        target.assignLayer.startEditing()
        for fid, feat in values.items():
            target.assignLayer.changeAttributeValues(fid, feat)
        target.assignLayer.commitChanges(True)

    def copyAssignments(self, target: RdsPlan, autocommit=True):
        def progress():
            nonlocal count
            count += 1
            self.progressChanged.emit(count)
            return 0

        self.clearErrors()

        if not target.assignLayer:
            self.setError(
                tr('Copy assignments: Target plan {name} has no assignment layer to copy into').format(
                    name=target.name),
                Qgis.Critical
            )
            return

        if not self._plan.assignLayer:
            self.setError(
                tr('Copy assignments: Source plan {name} has no assignment layer to copy from').format(
                    name=self._plan.name),
                Qgis.Critical
            )
            return

        if autocommit and self._plan.assignLayer.isEditable():
            # self.setError(tr('Committing unsaved changes before copy'))
            self._plan.assignLayer.commitChanges(True)

        with closing(spatialite_connect(target.geoPackagePath)) as db:
            db: sqlite3.Connection
            count = 0
            db.execute(f"ATTACH DATABASE '{self._plan.geoPackagePath}' AS source")
            db.set_progress_handler(progress, 1)
            sql = f"UPDATE assignments SET {target.distField} = s.{self._plan.distField} " \
                f"FROM source.assignments s WHERE assignments.{target.geoIdField} = s.{self._plan.geoIdField}"
            db.execute(sql)
            db.set_progress_handler(None, 1)
            db.commit()

        target.assignLayer.reload()
