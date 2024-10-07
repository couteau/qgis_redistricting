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
    Optional,
    Set,
    overload
)

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsField,
    QgsProject,
    QgsVectorDataProvider,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)

from ..models import (
    DataField,
    Field,
    GeoField
)
from ..utils import tr
from .BasePlanBuilder import BasePlanBuilder
from .DistrictUpdate import DistrictUpdater
from .Tasks.AddGeoFieldTask import AddGeoFieldToAssignmentLayerTask

# pylint: disable=protected-access


class PlanEditor(BasePlanBuilder):
    progressChanged = pyqtSignal(int)

    def __init__(self, parent: QObject = None, planUpdater: DistrictUpdater = None):
        super().__init__(parent)
        self._updater = planUpdater
        self._updateAssignLayerTask = None
        self._updating = 0
        self._oldvalues: Optional[dict] = None
        self._modifiedFields = set()

    @property
    def modifiedFields(self) -> Set[str]:
        return self._modifiedFields

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._updateAssignLayerTask:
            self._updateAssignLayerTask.cancel()

    def RaiseChangedReadonlyFieldError(self, attribute: str):
        raise RuntimeError(tr("Cannot change {attribute} after plan creation").format(attribute=attribute))

    def setGeoIdField(self, value: str):
        self.RaiseChangedReadonlyFieldError("GeoID Field")

    def setDistField(self, value: str):
        self.RaiseChangedReadonlyFieldError("District Field")

    def setGeoLayer(self, value: QgsVectorLayer):
        self.RaiseChangedReadonlyFieldError("Geography Layer")

    def setGeoJoinField(self, value: str):
        self.RaiseChangedReadonlyFieldError("Geography Join Field")

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
        elif isinstance(fieldOrFieldName, Iterable):
            fields = list(fieldOrFieldName)
            if not all(isinstance(f, QgsField) for f in fields):
                raise ValueError("Argument must be an iterable of QgsField")
        else:
            raise ValueError("Argument must be a string, QgsField, or iterable of QgsField")

        provider = layer.dataProvider()
        if not QgsVectorDataProvider.AddAttributes & provider.capabilities():
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

    def _updatePopFields(self):
        if self._plan.distLayer:
            layer = self._plan.distLayer
            addedFields: Set[Field] = set(self._popFields) - set(self._plan.popFields)
            if addedFields:
                self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

        self._plan._setPopFields(self._popFields)

    def _updateDataFields(self):
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

    def _updateGeoFields(self):
        def removeFields():
            removedFields: Set[Field] = set(self._plan.geoFields) - set(self._geoFields)
            if removedFields:
                provider = self._assignLayer.dataProvider()
                fields = self._assignLayer.fields()
                removeidx = [
                    fields.lookupField(f.fieldName)
                    for f in removedFields
                    if fields.lookupField(f.fieldName) != -1
                ]
                provider.deleteAttributes(removeidx)
                self._assignLayer.updateFields()

        def terminated():
            if self._updateAssignLayerTask.isCanceled():
                self.setError(tr('Update geography fields canceled'), Qgis.UserCanceled)

            provider = self._assignLayer.dataProvider()
            fields = self._assignLayer.fields()
            removeidx = [
                fields.lookupField(f.fieldName)
                for f in self._updateAssignLayerTask.geoFields
                if fields.lookupField(f.fieldName) != -1
            ]
            provider.deleteAttributes(removeidx)
            self._assignLayer.updateFields()

            self._geoFields = saveFields
            self._plan._setGeoFields(saveFields)

            self._updateAssignLayerTask = None

        def completed():
            removeFields()
            self._updateAssignLayerTask = None

        if not self._plan or not self._plan.assignLayer or self._geoFields == self._plan.geoFields:
            return

        saveFields = self._plan.geoFields
        layer = self._plan.assignLayer
        addedFields: Set[Field] = set(self._geoFields) - set(self._plan.geoFields)
        if addedFields:
            self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

            self._updateAssignLayerTask = AddGeoFieldToAssignmentLayerTask(
                self._geoPackagePath,
                self._plan.assignLayer,
                self._geoLayer,
                addedFields,
                self._geoJoinField,
                self._geoIdField
            )
            self._updateAssignLayerTask.taskCompleted.connect(completed)
            self._updateAssignLayerTask.taskTerminated.connect(terminated)
            self._updateAssignLayerTask.progressChanged.connect(self.setProgress)
            QgsApplication.taskManager().addTask(self._updateAssignLayerTask)
        else:
            removeFields()

        self._plan._setGeoFields(self._geoFields)

    def updatePlan(self):
        self.clearErrors()

        if not self._plan or not self.validate():
            return None

        self.startPlanUpdate()
        try:
            self._plan._setName(self._name)
            self._plan._setNumDistricts(self._numDistricts)
            self._plan._setNumSeats(self._numSeats)
            self._plan._setDescription(self._description)
            self._plan._setDeviation(self._deviation)

            self._plan._setPopLayer(self._popLayer)
            self._plan._setPopJoinField(self._popJoinField)
            self._plan._setPopField(self._popField)

            if self._popFields != self._plan.popFields:
                self._updatePopFields()

            if self._dataFields != self._plan.dataFields:
                self._updateDataFields()

            self._plan._setGeoIdCaption(self._geoIdCaption)

            if self._geoFields != self._plan.geoFields:
                self._updateGeoFields()

            self.endPlanUpdate()
        except Exception as e:  # pylint: disable=broad-except
            self.cancelPlanUpdate()
            self.pushError(e, Qgis.Critical)

        return self._plan

    def startPlanUpdate(self):
        self._oldvalues = self._plan.serialize()

    def endPlanUpdate(self):
        newvalues = self._plan.serialize()
        modifiedFields = {
            k for k in newvalues if k not in self._oldvalues or newvalues[k] != self._oldvalues[k]
        }
        modifiedFields |= {k for k in self._oldvalues if k not in newvalues}
        self._oldvalues = None
        self._modifiedFields = modifiedFields

        if self._updater:
            updateGeometry = updateSplits = updateDemographics = False
            if "geo-fields" in modifiedFields:
                updateSplits = True

            if modifiedFields & {"data-fields", "pop-fields", "pop-field", "pop-layer"}:
                updateSplits = True
                updateDemographics = True

            if "num-districts" in modifiedFields:
                updateGeometry = True

            if updateSplits or updateDemographics or updateGeometry:
                self._updater.updateDistricts(
                    self._plan,
                    needDemographics=updateDemographics,
                    needGeometry=updateGeometry,
                    needSplits=updateSplits,
                    force=True
                )

    def cancelPlanUpdate(self):
        if self._oldvalues is None:
            return

        self._plan._name = self._oldvalues.get('name')
        self._plan._description = self._oldvalues.get('description', '')
        self._plan._numDistricts = self._oldvalues.get('num-districts')
        self._plan._numSeats = self._oldvalues.get('num-seats')
        self._plan._deviation = self._oldvalues.get('deviation', 0.0)

        self._plan._totalPopulation = self._oldvalues.get('total-population', 0)

        self._plan._geoIdCaption = self._oldvalues.get('geo-id-caption', '')

        if 'pop-layer' in self._oldvalues:
            popLayer = QgsProject.instance().mapLayer(self._oldvalues.get('pop-layer'))
            self._plan._popLayer = popLayer
        self._plan._popJoinField = self._oldvalues.get('pop-join-field', '')
        self._plan._popField = self._oldvalues.get('pop-field')

        self._plan._popFields.clear()
        for field in self._oldvalues.get('pop-fields', []):
            f = Field.deserialize(field)
            if f:
                self._plan._popFields.append(f)

        self._plan._dataFields.clear()
        for field in self._oldvalues.get('data-fields', []):
            f = DataField.deserialize(field)
            if f:
                self._plan._dataFields.append(f)

        self._plan._geoFields.clear()
        for field in self._oldvalues.get('geo-fields', []):
            f = GeoField.deserialize(field)
            if f:
                self._plan._geoFields.append(f)

        self._oldvalues = None
