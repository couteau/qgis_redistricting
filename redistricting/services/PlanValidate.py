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
from numbers import Number
from typing import Optional

from qgis.core import (
    Qgis,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QObject

from ..models import (
    RdsDataField,
    RdsField,
    RdsGeoField,
    RdsPlan
)
from ..utils import tr
from .defaults import MAX_DISTRICTS
from .ErrorList import ErrorListMixin


class PlanValidator(ErrorListMixin, QObject):
    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._plan: RdsPlan = None

        self._name = ''
        self._description = ''
        self._numDistricts = 0
        self._numSeats = 0
        self._deviation = 0.0

        self._geoIdField = None
        self._geoIdCaption = ''
        self._distField = 'district'

        self._geoLayer: QgsVectorLayer = None
        self._geoJoinField = None
        self._geoFields: list[RdsGeoField] = []

        self._popLayer: QgsVectorLayer = None
        self._popJoinField = None
        self._popField = None
        self._popFields: list[RdsField] = []
        self._dataFields: list[RdsDataField] = []

        self._assignLayer: QgsVectorLayer = None
        self._distLayer: QgsVectorLayer = None

    @classmethod
    def fromPlan(cls, plan: RdsPlan, parent: Optional[QObject] = None, **kwargs):
        instance = cls(parent, **kwargs)
        instance._plan = plan

        instance._name = plan.name
        instance._description = plan.description
        instance._numDistricts = plan.numDistricts
        instance._numSeats = plan.numSeats
        instance._deviation = plan.deviation

        instance._geoIdField = plan.geoIdField
        instance._geoIdCaption = plan.geoIdCaption
        instance._distField = plan.distField

        instance._geoLayer = plan.geoLayer
        instance._geoJoinField = plan.geoJoinField
        instance._geoFields = plan.geoFields[:]

        instance._popLayer = plan.popLayer
        instance._popJoinField = plan.popJoinField
        instance._popField = plan.popField
        instance._popFields = plan.popFields[:]
        instance._dataFields = plan.dataFields[:]

        instance._assignLayer = plan.assignLayer
        instance._distLayer = plan.distLayer
        return instance

    def _validateLayer(self, layer: QgsVectorLayer, layerName: str, required=True, geometryRequired=True):
        result = True
        if layer:
            if not layer.isValid():
                self.pushError(
                    tr('{layer} layer is invalid').
                    format(layer=layerName.capitalize()),
                    Qgis.Critical
                )
                result = False
            elif geometryRequired and not layer.isSpatial():
                self.pushError(
                    tr('{layer} layer must be a spatial layer').
                    format(layer=layerName.capitalize()),
                    Qgis.Critical
                )
                result = False
        elif required:
            self.pushError(
                tr('{layer} layer is required').
                format(layer=layerName.capitalize()),
                Qgis.Critical
            )
            result = False

        return result

    def _validateGeoLayer(self):
        if result := self._validateLayer(self._geoLayer, tr('geogrpahy')):
            if self._geoJoinField:
                if self._geoLayer.fields().lookupField(self._geoJoinField) == -1:
                    self.pushError(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('join').capitalize(),
                            field=self._geoJoinField,
                            layertype=tr('geography'),
                            layername=self._geoLayer.name()
                        )
                    )
                    result = False

            for f in self._geoFields:
                if not f.validate(self._geoLayer):
                    self.pushError(f.error())
                    result = False

        return result

    def _validatePopField(self, field: str, fieldname: str):
        if not self._popLayer:
            return True

        if (idx := self._popLayer.fields().lookupField(field)) == -1:
            self.pushError(
                tr('{fieldname} field {field} not found in {layertype} layer {layername}').
                format(
                    fieldname=fieldname,
                    field=field,
                    layertype=tr('population'),
                    layername=self._popLayer.name()
                ),
                Qgis.Critical
            )
            return False

        f = self._popLayer.fields().field(idx)
        if not f.isNumeric():
            self.pushError(
                tr('{fieldname} field {field} must be numeric').format(
                    fieldname=fieldname,
                    field=field
                ),
                Qgis.Critical
            )
            return False

        return True

    def _validatePopLayer(self):
        if result := self._validateLayer(self._popLayer, tr('population'), geometryRequired=False):
            if self._popJoinField and self._popLayer.fields().lookupField(self._popJoinField) == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('join').capitalize(),
                        field=self._popJoinField,
                        layertype=tr('population'),
                        layername=self._popLayer.name()
                    ),
                    Qgis.Critical
                )
                result = False

            if self._popField:
                result = result and self._validatePopField(self._popField, tr('population').capitalize())

            for f in self._popFields:
                result = result and self._validatePopField(f.field, f.caption)

            for f in self._dataFields:
                if f.layer != self._popLayer:
                    raise ValueError(tr("Layer for field {field} should be plan poplayer").format(field=f.field))

                if not f.validate():
                    self.pushErrors(*f.errors())
                    result = False

        return result

    def _validateAssignLayer(self, strict):
        result = self._validateLayer(self._assignLayer, tr('assignments'), self._plan is not None)

        if result and self._assignLayer:
            if self._assignLayer.fields().lookupField(self._geoIdField) == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('Geo ID'),
                        field=self._geoIdField,
                        layertype=tr('assignments'),
                        layername=self._assignLayer.name()
                    ),
                    Qgis.Critical
                )
                result = False

            if self._assignLayer.fields().lookupField(self._distField) == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('district').capitalize(),
                        field=self._distField,
                        layertype=tr('assignment'),
                        layername=self._assignLayer.name()
                    ),
                    Qgis.Critical
                )
                result = False

            for f in self._geoFields:
                if self._assignLayer.fields().lookupField(f.fieldName) == -1:
                    self.pushError(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('geography').capitalize(),
                            field=f.fieldName,
                            layertype=tr('assignment'),
                            layername=self._assignLayer.name()
                        ),
                        Qgis.Critical if strict else Qgis.Warning
                    )
                    if strict:
                        result = False

        return result

    def _validateDistLayer(self, strict):
        result = self._validateLayer(self._distLayer, tr('district'), self._plan is not None)
        if result and self._distLayer:
            if self._distLayer.fields().lookupField(self._distField) == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('district').capitalize(),
                        field=self._distField,
                        layertype=tr('district'),
                        layername=self._distLayer.name()
                    ),
                    Qgis.Critical
                )
                result = False

            for f in self._dataFields:
                if self._distLayer.fields().lookupField(f.fieldName) == -1:
                    self.pushError(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('geography').capitalize(),
                            field=f.fieldName,
                            layertype=tr('district'),
                            layername=self._distLayer.name()
                        ),
                        Qgis.Critical if strict else Qgis.Warning
                    )
                    if strict:
                        result = False

            if self._distLayer.fields().lookupField('polsbypopper') == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('metric').capitalize(),
                        field='polsbypopper',
                        layertype=tr('district'),
                        layername=self._distLayer.name()
                    ),
                    Qgis.Warning
                )

            if self._distLayer.fields().lookupField('reock') == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('metric').capitalize(),
                        field='reock',
                        layertype=tr('district'),
                        layername=self._distLayer.name()
                    ),
                    Qgis.Warning
                )

            if self._distLayer.fields().lookupField('convexhull') == -1:
                self.pushError(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('metric').capitalize(),
                        field='convexhull',
                        layertype=tr('district'),
                        layername=self._distLayer.name()
                    ),
                    Qgis.Warning
                )

        return result

    def validate(self, strict=False):
        result = True

        result = self._name \
            and self._geoLayer \
            and self._popLayer \
            and self._geoJoinField \
            and self._popJoinField \
            and self._geoIdField \
            and self._distField \
            and self._popField \
            and self._numDistricts > 1 \
            and self._numSeats >= self._numDistricts

        if self._numDistricts < 2 or self._numDistricts > MAX_DISTRICTS:
            self.pushError(tr('Invalid number of districts for plan: {value}').format(
                value=self._numDistricts), Qgis.Critical)

        if self._numSeats < self._numDistricts:
            self.pushError(
                tr('Number of seats ({seats}) must equal or exceed number of districts ({districts})').
                format(seats=self._numSeats, districts=self._numDistricts),
                Qgis.Critical
            )

        if not isinstance(self._deviation, Number) or self._deviation < 0:
            self.pushError(tr('Deviation must be 0 or a positive number'))
            result = False

        if not self._name:
            self.pushError(tr('Plan name must be set'), Qgis.Critical)

        if not self._geoIdField:
            self.pushError(tr('{field} field is required').format(field=tr('Geography ID')), Qgis.Critical)

        if not self._distField:
            self.pushError(tr('{field} field is required').format(field=tr('District')), Qgis.Critical)

        if not self._geoJoinField:
            self.pushError(tr('{field} field is required').format(field=tr('Geograph Join')), Qgis.Critical)

        if not self._popJoinField:
            self.pushError(tr('{field} field is required').format(field=tr('Population Join')), Qgis.Critical)

        if not self._popField:
            self.pushError(tr('{field} field is required').format(field=tr('Population')), Qgis.Critical)

        result = result \
            and self._validateGeoLayer() \
            and self._validatePopLayer() \
            and self._validateAssignLayer(strict) \
            and self._validateDistLayer(strict)

        return result
