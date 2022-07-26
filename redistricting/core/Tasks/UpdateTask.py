# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to aggregate district data

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
from typing import Dict, TYPE_CHECKING
from qgis.core import (
    QgsExpressionContext,
    QgsTask,
    QgsVectorLayer
)
from ._exception import CancelledError

if TYPE_CHECKING:
    from .. import RedistrictingPlan, DataField


class AggregateDataTask(QgsTask):
    """Task to aggregate the plan summary data and geometry in the background"""

    def __init__(self, plan: RedistrictingPlan, description):
        super().__init__(description, QgsTask.AllFlags)
        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.distLayer: QgsVectorLayer = plan.distLayer
        self.popLayer: QgsVectorLayer = plan.popLayer
        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.joinField: str = plan.joinField
        self.popField: str = plan.popField
        self.vapField: str = plan.vapField
        self.cvapField: str = plan.cvapField
        self.dataFields = plan.dataFields
        self.count = 0
        self.total = 1
        self.exception = None

    def hasExpression(self):
        for f in self.dataFields:
            if f.isExpression:
                return True

        return False

    def getData(self, data):
        if self.isCanceled():
            raise CancelledError()

        self.count += 1
        if self.count % 100 == 0:
            self.setProgress(90 * self.count/self.total)

        return data

    def getFieldValue(self, fld: 'DataField', context: QgsExpressionContext):
        return lambda f: fld.getValue(f, context)

    def addPopFields(self, cols: list, getters: list, aggs: Dict[str, str], context: QgsExpressionContext):
        cols.append(self.popField)
        getters.append(lambda f: f[self.popField])
        aggs[self.popField] = 'sum'
        if self.vapField:
            cols.append(self.vapField)
            getters.append(lambda f: f[self.vapField])
            aggs[self.vapField] = 'sum'
        if self.cvapField:
            cols.append(self.cvapField)
            getters.append(lambda f: f[self.cvapField])
            aggs[self.vapField] = 'sum'
        for fld in self.dataFields:
            cols.append(fld.fieldName)
            getters.append(self.getFieldValue(fld, context))
            aggs[fld.fieldName] = 'sum' if fld.isNumeric else 'first'
