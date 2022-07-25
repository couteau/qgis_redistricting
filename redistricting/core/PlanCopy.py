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

import shutil
from typing import TYPE_CHECKING
from contextlib import closing
from copy import deepcopy
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import (
    Qgis,
    QgsFeedback,
    QgsMessageLog
)
from qgis.utils import spatialite_connect
from .Utils import tr
from .PlanStyle import PlanStyler
if TYPE_CHECKING:
    from .Plan import RedistrictingPlan


class PlanCopier(QObject):
    copyComplete = pyqtSignal('PyQt_PyObject')

    def __init__(
        self,
        sourcePlan: RedistrictingPlan
    ):
        super().__init__(sourcePlan)
        self._plan = sourcePlan
        self._error = None
        self._errorLevel = None
        self._exportTask = None

    def error(self):
        return (self._error, self._errorLevel)

    def setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def clearError(self):
        self._error = None

    def copyPlan(self, planName, copyAssignments: bool = True, destGpkgPath: str = None, copyStyles: bool = True):
        plan = deepcopy(self._plan)
        plan.name = planName
        if copyAssignments and destGpkgPath:
            shutil.copyfile(self._plan.geoPackagePath, destGpkgPath)
            plan.addLayersFromGeoPackage(destGpkgPath)

        if copyStyles:
            PlanStyler(plan).copyStyles(self._plan)

        self.copyComplete(plan)
        return plan

    def copyAssignments(self, target: RedistrictingPlan, feedback: QgsFeedback = None):

        def makeTuple(dist, geoid):
            nonlocal c
            c += 1
            feedback.setProgress(c/total)
            return (dist, geoid)

        self.clearError()

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

        if self._plan.assignLayer.isEditable():
            self.setError(tr('Committing unsaved changes before copy'))
            self._plan.assignLayer.commitChanges(True)

        with closing(spatialite_connect(target.geoPackagePath)) as db:
            if feedback:
                total = self._plan.assignLayer.featureCount()
                c = 0
                generator = (
                    makeTuple(f[self._plan.distField],
                              f[self._plan.geoIdField])
                    for f in self._plan.assignLayer.getFeatures()
                )
            else:
                generator = (
                    (f[self._plan.distField], f[self._plan.geoIdField])
                    for f in self._plan.assignLayer.getFeatures()
                )

            sql = f"UPDATE assignments SET {target.distField} = ? WHERE  {target.geoIdField} = ?"
            db.executemany(sql, generator)
            db.commit()

        target.assignLayer.reload()
        target.districts.resetData(updateGeometry=True)
