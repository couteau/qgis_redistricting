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
    Iterable,
    List,
    Set,
    Union,
    overload
)

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsField,
    QgsVectorDataProvider,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)

from .BasePlanBuilder import BasePlanBuilder
from .Field import (
    DataField,
    Field
)
from .Tasks.AddGeoFieldTask import AddGeoFieldToAssignmentLayerTask
from .utils import tr


class PlanEditor(BasePlanBuilder):
    progressChanged = pyqtSignal(int)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self._updateAssignLayerTask = None
        self._modifiedFields = set()

    @property
    def modifiedFields(self) -> Set[str]:
        return self._modifiedFields

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._updateAssignLayerTask:
            self._updateAssignLayerTask.cancel()

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, fieldName: str, fieldType: QVariant.Type):
        ...

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, field: QgsField):
        ...

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, fields: Iterable[QgsField]):
        ...

    def _addFieldToLayer(self, layer: QgsVectorLayer, fieldOrFieldName, fieldType=None):
        if isinstance(fieldOrFieldName, str):
            if layer.fields().lookupField(fieldOrFieldName) != -1:
                # fieldName undefined or field already exists
                self.setError(
                    tr('Error creating new field: field {field} already exits in layer {layer}').
                    format(field=fieldOrFieldName, layer=layer.name())
                )
                return
            if fieldType is None:
                self.setError(tr('Field type is required when adding fields by name'))
                return

            fields = [QgsField(fieldOrFieldName, fieldType)]
        elif isinstance(fieldOrFieldName, QgsField):
            fields = [QgsField(fieldOrFieldName)]
        else:
            fields = fieldOrFieldName

        provider = layer.dataProvider()
        if not int(QgsVectorDataProvider.AddAttributes) & int(provider.capabilities()):
            self.pushError('Could not add field to layer', Qgis.Critical)
            return
        for field in reversed(fields):
            # ignore fields with conflicting names
            if provider.fields().lookupField(field.name()) != -1:
                self.pushError(
                    tr('A field named {field} already exists in layer {layer}. Omitting.').
                    format(field=field.name(), layer=layer.name()),
                    Qgis.Warning
                )
                fields.remove(field)
        if fields:
            provider.addAttributes(fields)
            layer.updateFields()

    def _updateGeoField(self, geoField: Union[Field, List[Field]]):

        def cleanup():
            if self._updateAssignLayerTask.isCanceled():
                self.setError(tr('Add geography field canceled'),
                              Qgis.UserCanceled)
            self._updateAssignLayerTask = None

        if not self._plan or not self._plan.assignLayer:
            return None

        if isinstance(geoField, Field):
            geoField = [geoField]

        self._updateAssignLayerTask = AddGeoFieldToAssignmentLayerTask(
            self._geoPackagePath,
            self._plan.assignLayer,
            self._geoLayer,
            geoField,
            self._sourceIdField,
            self._geoIdField
        )
        self._updateAssignLayerTask.taskCompleted.connect(cleanup)
        self._updateAssignLayerTask.taskTerminated.connect(cleanup)
        self._updateAssignLayerTask.progressChanged.connect(self.setProgress)
        QgsApplication.taskManager().addTask(self._updateAssignLayerTask)
        return self._updateAssignLayerTask

    # pylint: disable=protected-access
    def updatePlan(self):
        self.clearErrors()

        if not self._plan or not self.validate():
            return None

        a = self._plan.serialize()

        self._plan._setName(self._name)
        self._plan._setNumDistricts(self._numDistricts)
        self._plan._setNumSeats(self._numSeats)
        self._plan._setDescription(self._description)
        self._plan._setDeviation(self._deviation)

        if self._popFields != self._plan.popFieldsFields:
            if self._plan.distLayer:
                layer = self._plan.distLayer
                addedFields: Set[Field] = set(self._popFields) - set(self._plan.popFields)
                if addedFields:
                    self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

                removedFields: Set[Field] = set(self._plan.popFields) - set(self._popFields)
                if removedFields:
                    provider = layer.dataProvider()
                    for f in removedFields:
                        findex = layer.fields().lookupField(f.fieldName)
                        if findex != -1:
                            provider.deleteAttributes([findex])
                    layer.updateFields()

            self._plan._setPopFields(self._popFields)

        if self._dataFields != self._plan.dataFields:
            if self._plan.distLayer:
                layer = self._plan.distLayer

                addedFields: Set[DataField] = set(self._dataFields) - set(self._plan.dataFields)
                if addedFields:
                    self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

                removedFields: Set[DataField] = set(self._plan.dataFields) - set(self._dataFields)
                if removedFields:
                    provider = layer.dataProvider()
                    for f in removedFields:
                        findex = layer.fields().lookupField(f.fieldName)
                        if findex != -1:
                            provider.deleteAttributes([findex])
                    layer.updateFields()

            self._plan._setDataFields(self._dataFields)

        if self._geoFields != self._plan.geoFields:
            if self._plan.assignLayer:
                layer = self._plan.assignLayer

                removedFields: Set[Field] = set(self._plan.geoFields) - set(self._geoFields)
                if removedFields:
                    provider = layer.dataProvider()
                    for f in removedFields:
                        findex = layer.fields().lookupField(f.fieldName)
                        if findex != -1:
                            provider.deleteAttributes([findex])
                    layer.updateFields()

                addedFields: Set[Field] = set(self._geoFields) - set(self._plan.geoFields)
                if addedFields:
                    self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])
                    self._updateGeoField(addedFields)

            self._plan._setGeoFields(self._geoFields)

        self._plan._setGeoIdField(self._geoIdField)
        self._plan._setGeoIdCaption(self._geoIdCaption)

        self._plan._setGeoLayer(self._geoLayer)
        self._plan._setGeoJoinField(self._sourceIdField)

        self._plan._setPopLayer(self._popLayer)
        self._plan._setPopJoinField(self._popJoinField)
        self._plan._setPopField(self._popField)

        b = self._plan.serialize()
        self._modifiedFields = {k for k in b if k not in a or b[k] != a[k]}
        self._modifiedFields |= {k for k in a if k not in b}

        return self._plan
