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

from typing import Iterable, Optional, overload

from qgis.core import Qgis, QgsApplication, QgsField, QgsProject, QgsVectorDataProvider, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType, QObject, pyqtSignal

from ..models import RdsDataField, RdsField, RdsGeoField, deserialize, serialize
from ..utils import tr
from .basebuilder import BasePlanBuilder
from .district import DistrictUpdater
from .tasks.addgeofield import AddGeoFieldToAssignmentLayerTask

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
    def modifiedFields(self) -> set[str]:
        return self._modifiedFields

    def setProgress(self, progress: float):
        self.progressChanged.emit(int(progress))

    def cancel(self):
        if self._updateAssignLayerTask:
            self._updateAssignLayerTask.cancel()

    def RaiseChangedReadonlyFieldError(self, attribute: str):
        raise RuntimeError(tr('Cannot change {attribute} after plan creation').format(attribute=attribute))

    def setGeoIdField(self, value: str):
        self.RaiseChangedReadonlyFieldError('GeoID RdsField')

    def setDistField(self, value: str):
        self.RaiseChangedReadonlyFieldError('District RdsField')

    def setGeoLayer(self, value: QgsVectorLayer):
        self.RaiseChangedReadonlyFieldError('Geography Layer')

    def setGeoJoinField(self, value: str):
        self.RaiseChangedReadonlyFieldError('Geography Join RdsField')

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, fieldName: str, fieldType: QMetaType.Type): ...

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, field: QgsField): ...

    @overload
    def _addFieldToLayer(self, layer: QgsVectorLayer, fields: Iterable[QgsField]): ...

    def _addFieldToLayer(self, layer: QgsVectorLayer, fieldOrFieldName, fieldType=None):
        if isinstance(fieldOrFieldName, str):
            if layer.fields().lookupField(fieldOrFieldName) != -1:
                # fieldName undefined or field already exists
                self.setError(
                    tr('Error creating new field: field {field} already exits in layer {layer}').format(
                        field=fieldOrFieldName, layer=layer.name()
                    )
                )
                return
            if fieldType is None:
                self.setError(tr('RdsField type is required when adding fields by name'))
                return

            fields = [QgsField(fieldOrFieldName, fieldType)]
        elif isinstance(fieldOrFieldName, QgsField):
            fields = [QgsField(fieldOrFieldName)]
        elif isinstance(fieldOrFieldName, Iterable):
            fields = list(fieldOrFieldName)
            if not all(isinstance(f, QgsField) for f in fields):
                raise ValueError('Argument must be an iterable of QgsField')
        else:
            raise ValueError('Argument must be a string, QgsField, or iterable of QgsField')

        provider = layer.dataProvider()
        if not QgsVectorDataProvider.AddAttributes & provider.capabilities():
            self.pushError('Could not add field to layer', Qgis.MessageLevel.Critical)
            return
        for field in reversed(fields):
            # ignore fields with conflicting names
            if provider.fields().lookupField(field.name()) != -1:
                self.pushError(
                    tr('A field named {field} already exists in layer {layer}. Omitting.').format(
                        field=field.name(), layer=layer.name()
                    ),
                    Qgis.MessageLevel.Warning,
                )
                fields.remove(field)
        if fields:
            provider.addAttributes(fields)
            layer.updateFields()

    def _updatePopFields(self):
        if self._plan.distLayer:
            layer = self._plan.distLayer
            addedFields: list[RdsField] = [f for f in self._popFields if f not in self._plan.popFields]
            if addedFields:
                self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

        self._plan.popFields = self._popFields

    def _updateDataFields(self):
        if self._plan.distLayer:
            layer = self._plan.distLayer

            addedFields: list[RdsDataField] = [f for f in self._dataFields if f not in self._plan.dataFields]
            if addedFields:
                self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

            removedFields: list[RdsDataField] = [f for f in self._plan.dataFields if f not in self._dataFields]
            if removedFields:
                provider = layer.dataProvider()
                for f in removedFields:
                    findex = layer.fields().lookupField(f.fieldName)
                    if findex != -1:
                        provider.deleteAttributes([findex])
                layer.updateFields()

        self._plan.dataFields = self._dataFields

    def _updateGeoFields(self):
        def removeFields():
            removedFields: list[RdsField] = [f for f in self._plan.geoFields if f not in self._geoFields]
            if removedFields:
                provider = self._assignLayer.dataProvider()
                fields = self._assignLayer.fields()
                removeidx = [
                    fields.lookupField(f.fieldName) for f in removedFields if fields.lookupField(f.fieldName) != -1
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
        addedFields: list[RdsField] = [f for f in self._geoFields if f not in self._plan.geoFields]
        if addedFields:
            self._addFieldToLayer(layer, [f.makeQgsField() for f in addedFields])

            self._updateAssignLayerTask = AddGeoFieldToAssignmentLayerTask(
                self._geoPackagePath,
                self._plan.assignLayer,
                self._geoLayer,
                addedFields,
                self._geoJoinField,
                self._geoIdField,
            )
            self._updateAssignLayerTask.taskCompleted.connect(completed)
            self._updateAssignLayerTask.taskTerminated.connect(terminated)
            self._updateAssignLayerTask.progressChanged.connect(self.setProgress)
            QgsApplication.taskManager().addTask(self._updateAssignLayerTask)
        else:
            removeFields()

        self._plan.geoFields = self._geoFields

    def updatePlan(self):
        self.clearErrors()

        if not self._plan or not self.validate():
            return None

        self.startPlanUpdate()
        try:
            self._plan.name = self._name
            self._plan.numDistricts = self._numDistricts
            self._plan.numSeats = self._numSeats
            self._plan.description = self._description
            self._plan.deviation = self._deviation
            self._plan.deviationType = self._deviationType

            self._plan.popLayer = self._popLayer
            self._plan.popJoinField = self._popJoinField
            self._plan.popField = self._popField

            if self._popFields != list(self._plan.popFields):
                self._updatePopFields()

            if self._dataFields != list(self._plan.dataFields):
                self._updateDataFields()

            self._plan.geoIdCaption = self._geoIdCaption

            if self._geoFields != list(self._plan.geoFields):
                self._updateGeoFields()

            self.endPlanUpdate()
        except Exception as e:  # pylint: disable=broad-except
            self.cancelPlanUpdate()
            self.pushError(e, Qgis.MessageLevel.Critical)

        return self._plan

    def startPlanUpdate(self):
        self._oldvalues = serialize(self._plan)

    def endPlanUpdate(self):
        newvalues = serialize(self._plan)
        modifiedFields = {k for k in newvalues if k not in self._oldvalues or newvalues[k] != self._oldvalues[k]}
        modifiedFields |= {k for k in self._oldvalues if k not in newvalues}
        self._oldvalues = None
        self._modifiedFields = modifiedFields

        if self._updater:
            updateGeometry = updateSplits = updateDemographics = False
            if 'geo-fields' in modifiedFields:
                updateSplits = True

            if modifiedFields & {'data-fields', 'pop-fields', 'pop-field', 'pop-layer'}:
                updateSplits = True
                updateDemographics = True

            if 'num-districts' in modifiedFields:
                updateGeometry = True

            if updateSplits or updateDemographics or updateGeometry:
                self._updater.updateDistricts(
                    self._plan, needDemographics=updateDemographics, needGeometry=updateGeometry, force=True
                )

    def cancelPlanUpdate(self):
        if self._oldvalues is None:
            return

        self._plan.name = self._oldvalues.get('name')
        self._plan.description = self._oldvalues.get('description', '')
        self._plan.numDistricts = self._oldvalues.get('num-districts')
        self._plan.numSeats = self._oldvalues.get('num-seats')
        self._plan.deviation = self._oldvalues.get('deviation', 0.0)

        self._plan._geoIdCaption = self._oldvalues.get('geo-id-caption', '')

        if 'pop-layer' in self._oldvalues:
            popLayer = QgsProject.instance().mapLayer(self._oldvalues.get('pop-layer'))
            self._plan._popLayer = popLayer
        self._plan._popJoinField = self._oldvalues.get('pop-join-field', '')
        self._plan._popField = self._oldvalues.get('pop-field')

        self._plan.popFields.clear()
        for field in self._oldvalues.get('pop-fields', []):
            f = deserialize(RdsField, field)
            if f:
                self._plan.popFields.append(f)

        self._plan.dataFields.clear()
        for field in self._oldvalues.get('data-fields', []):
            f = deserialize(RdsDataField, field)
            if f:
                self._plan.dataFields.append(f)

        self._plan._geoFields.clear()
        for field in self._oldvalues.get('geo-fields', []):
            f = deserialize(RdsGeoField, field)
            if f:
                self._plan.geoFields.append(f)

        self._oldvalues = None
