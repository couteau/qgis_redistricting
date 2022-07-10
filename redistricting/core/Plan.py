# -*- coding: utf-8 -*-
"""RedistrictingPlan - QGIS Redistricting plugin core logic

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from numbers import Number
from typing import Any, Dict, Tuple, Iterable, List, Optional, Union, overload
from math import ceil, floor
from uuid import UUID, uuid4

from qgis.PyQt.QtCore import QObject, QVariant, pyqtSignal
from qgis.PyQt.QtWidgets import QProgressDialog
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsVectorDataProvider,
    QgsField,
    QgsMessageLog,
)

from .Exception import RdsException
from .FieldList import FieldList
from .Field import Field, DataField
from .DistrictList import DistrictList
from .District import BaseDistrict, District
from .PlanGroup import PlanGroup
from .Utils import tr, makeFieldName
from .Tasks import (
    CreatePlanLayersTask,
    AddGeoFieldToAssignmentLayerTask
)

# pylint: disable=too-many-public-methods,too-many-lines,too-many-instance-attributes


class RedistrictingPlan(QObject):
    dataFieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    dataFieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    geoFieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    geoFieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    planChanged = pyqtSignal('PyQt_PyObject', str, 'PyQt_PyObject', 'PyQt_PyObject')
    layersCreated = pyqtSignal('PyQt_PyObject')

    def __init__(self, name='', numDistricts: int = None, uuid: UUID = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        if not name or not isinstance(name, str):
            raise ValueError(tr('Cannot create redistricting plan: ') + tr('Redistricting plan name must be provided'))
        if numDistricts is not None and (not isinstance(numDistricts, int) or numDistricts < 2):
            raise ValueError(tr('Cannot create redistricting plan: ') +
                             tr('Number of districts must be an integer between 2 and 2,000'))
        if uuid is not None and not isinstance(uuid, UUID):
            raise ValueError(tr('Cannot create redistricting plan: ') + tr('Invalid UUID'))

        self._totalPopulation = 0
        self._cutEdges = 0

        self._uuid = uuid or uuid4()
        self._name = name or self._uuid
        self._group = PlanGroup(self)

        self._description = ''
        self._numDistricts = numDistricts or 0
        self._numSeats = numDistricts
        self._deviation = 0.0

        self._distLayer: QgsVectorLayer = None

        self._assignLayer: QgsVectorLayer = None
        self._geoIdField = None
        self._geoDisplay = ''
        self._distField = 'district'

        self._sourceLayer = None
        self._sourceIdField = None
        self._geoFields = FieldList(self)

        self._popLayer: QgsVectorLayer = None
        self._joinField = None
        self._popField = None
        self._vapField = None
        self._cvapField = None
        self._dataFields = FieldList(self)

        self._districts = DistrictList(self)
        self._error = None
        self._errorLevel = None

    def __copy__(self):
        data = self.serialize()
        del data['id']
        del data['assign-layer']
        del data['dist-layer']
        return RedistrictingPlan.deserialize(data, self.parent())

    def __deepcopy__(self, memo):
        return self.__copy__()

    def serialize(self) -> Dict[str, Any]:
        data = {
            'id': str(self._uuid),
            'name': self._name,
            'description': self._description,
            'total-population': self._totalPopulation,
            'num-districts': self._numDistricts,
            'num-seats': self.numSeats if self.numSeats != self._numDistricts else None,
            'deviation': self._deviation,
            'cut-edges': self._cutEdges,
            'pop-layer': self._popLayer.id() if self._popLayer else None,
            'assign-layer': self._assignLayer.id() if self._assignLayer else None,
            'dist-layer': self._distLayer.id() if self._distLayer else None,
            'geo-id-field': self._geoIdField,
            'geo-id-display': self._geoDisplay,
            'dist-field': self._distField,
            'pop-field': self._popField,
            'vap-field': self._vapField,
            'cvap-field': self._cvapField,
            'src-layer': self._sourceLayer.id() if self._sourceLayer else None,
            'src-id-field': self._sourceIdField,
            'data-fields': [field.serialize() for field in self._dataFields],
            'geo-fields': [field.serialize() for field in self._geoFields],
            'districts': [dist.serialize() for dist in self._districts if dist.district != 0]
        }

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def deserialize(cls, data: Dict[str, Any], parent: QObject):
        uuid = data.get('id')
        uuid = UUID(uuid) if uuid else uuid4()
        name = data.get('name', str(uuid))
        numDistricts = data.get('num-districts')

        plan = cls(name, numDistricts, uuid, parent)

        plan._description = data.get('description', '')
        plan._numSeats = data.get('num-seats') or plan._numDistricts
        plan._totalPopulation = data.get('total-population', 0)
        plan._deviation = data.get('deviation', 0.0)
        plan._cutEdges = data.get('cut-edges', 0)

        plan._distField = data.get('dist-field', plan._distField)
        plan._geoIdField = data.get('geo-id-field', plan._geoIdField)
        plan._geoDisplay = data.get('geo-id-display', '')

        plan._popLayer = QgsProject.instance().mapLayer(data.get('pop-layer'))
        plan._popField = data.get('pop-field')
        plan._vapField = data.get('vap-field')
        plan._cvapField = data.get('cvap-field')

        for field in data.get('data-fields', []):
            f = DataField.deserialize(field, plan.dataFields)
            if f:
                plan._dataFields.append(f)

        for field in data.get('geo-fields', []):
            f = Field.deserialize(field, plan.geoFields)
            if f:
                plan._geoFields.append(f)

        for dist in data.get('districts', []):
            plan._districts.deserializeDistrict(dist)

        plan._setAssignLayer(QgsProject.instance().mapLayer(data.get('assign-layer')))
        plan._setDistLayer(QgsProject.instance().mapLayer(data.get('dist-layer')))
        if 'src-layer' in data:
            layer = QgsProject.instance().mapLayer(data['src-layer'])
            plan._sourceLayer = layer

        plan._sourceIdField = data.get('src-id-field')

        return plan

    def isValid(self):
        return bool(
            self.name and
            self.assignLayer and
            self.distLayer and
            self.popLayer and
            self.geoIdField and
            self.popField and
            self.distField and
            self.numDistricts >= 2
        )

    @property
    def id(self) -> UUID:
        return self._uuid

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if self._name != value:
            if not value:
                raise ValueError(tr('Plan name must be set'))

            oldValue = self._name
            self._name = value
            self._updateLayerNames()
            self._group.updateName()
            self.planChanged.emit(self, 'name', value, oldValue)

    @property
    def numDistricts(self) -> int:
        return self._numDistricts

    @numDistricts.setter
    def numDistricts(self, value: int):
        if self._numDistricts != value:
            if not isinstance(value, int):
                raise ValueError(tr('Number of districts must be an integer'))

            if value < 2 or value > 1000:
                raise ValueError(
                    tr('Invalid number of districts for plan: {value}').format(value=value))
            oldDistricts = self._numDistricts
            self._numDistricts = value
            if self._numDistricts < oldDistricts:
                for i in range(value + 1, oldDistricts):
                    del self._districts[str(i)]
            if self.numSeats < self._numDistricts:
                self._numSeats = None

            self.planChanged.emit(self, 'num-districts', value, oldDistricts)

    @property
    def numSeats(self) -> int:
        return self._numSeats or self._numDistricts

    @numSeats.setter
    def numSeats(self, value: int):
        if value is not None and not isinstance(value, int):
            raise ValueError(tr('Number of seats must be an integer'))

        if value != self.numSeats or (value is None and self.numSeats != self._numDistricts):
            oldValue = self.numSeats
            if value == self._numDistricts or not value:
                self._numSeats = None
            elif value < self._numDistricts:
                raise ValueError(
                    tr('Number of seats must equal or exceed number of districts: {value}').format(value=value))
            else:
                self._numSeats = value

            self.planChanged.emit(self, 'num-seats', self.numSeats, oldValue)

    @property
    def allocatedDistricts(self):
        return len(self._districts) - 1

    @property
    def allocatedSeats(self):
        return sum(d.members for d in self._districts if isinstance(d, District))

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str):
        if self._description != value:
            oldValue = self._description
            self._description = value
            self.planChanged.emit(self, 'description', value, oldValue)

    @property
    def deviation(self) -> float:
        return self._deviation

    @deviation.setter
    def deviation(self, value: float):
        if not isinstance(value, Number):
            raise ValueError(tr('Deviation must be numeric'))

        if value != self._deviation:
            oldValue = self._deviation
            self._deviation = float(value)
            self.planChanged.emit(self, 'deviation', value, oldValue)

    @property
    def geoIdField(self) -> str:
        return self._geoIdField

    @geoIdField.setter
    def geoIdField(self, value: str):
        if value != self._geoIdField:
            if not value:
                raise ValueError(tr('Geo ID field must be set'))
            if self._assignLayer and self._assignLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('Geo ID'),
                        field=value,
                        layertype=tr('assignments'),
                        layername=self._assignLayer.name()
                    )
                )
            oldValue = self._geoIdField
            self._geoIdField = value
            self._districts.resetData(updateGeometry=True)
            self.planChanged.emit(self, 'geo-id-Field', value, oldValue)

    @property
    def distField(self) -> str:
        return self._distField or 'district'

    @distField.setter
    def distField(self, value: str):
        if value != self._distField:
            if not value:
                raise ValueError(tr('District field must be set'))
            if self._assignLayer and self._assignLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('district').capitalize(),
                        field=value,
                        layertype=tr('population'),
                        layername=self._assignLayer.name()
                    )
                )

            oldValue = self._distField
            self._distField = value
            self._districts.resetData(updateGeometry=True)
            self.planChanged.emit(self, 'dist-field', value, oldValue)

    @property
    def sourceLayer(self) -> QgsVectorLayer:
        return self._sourceLayer or self._popLayer

    @sourceLayer.setter
    def sourceLayer(self, value: QgsVectorLayer):
        value = value or self._popLayer
        if self._sourceIdField:
            idx = value.fields().lookupField(self._sourceIdField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('join').capitalize(),
                        field=self._sourceIdField,
                        layertype=tr('source'),
                        layername=value.name()
                    )
                )

        if value and value != self.sourceLayer:
            for f in self._geoFields:
                f.setLayer(value)

        if value == self._popLayer:
            self._sourceLayer = None
        else:
            self._sourceLayer = value

    @ property
    def sourceIdField(self) -> str:
        return self._sourceIdField or self._geoIdField

    @sourceIdField.setter
    def sourceIdField(self, value: str):
        if value == self._geoIdField or not value:
            self._sourceIdField = None
        else:
            if self.sourceLayer and self.sourceLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('join').capitalize(),
                        field=value,
                        layertype=tr('source'),
                        layername=self.sourceLayer.name()
                    )
                )
            self._sourceIdField = value

    @property
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer

    @popLayer.setter
    def popLayer(self, value: QgsVectorLayer):
        if not value:
            raise ValueError(tr('Population layer must be provided'))

        if self._popField:
            idx = value.fields().lookupField(self._popField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('population').capitalize(),
                        field=self._popField,
                        layertype=tr('population'),
                        layername=value.name()
                    )
                )
        if self._joinField:
            idx = value.fields().lookupField(self._joinField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('join').capitalize(),
                        field=self._joinField,
                        layertype=tr('population'),
                        layername=value.name()
                    )
                )
        if self._vapField:
            idx = value.fields().lookupField(self._vapField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('VAP').capitalize(),
                        field=self._vapField,
                        layertype=tr('population'),
                        layername=value.name()
                    )
                )
        if self._cvapField:
            idx = value.fields().lookupField(self._cvapField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('CVAP').capitalize(),
                        field=self._cvapField,
                        layertype=tr('population'),
                        layername=value.name()
                    )
                )

        for f in self._dataFields:
            f.setLayer(value)
        if not self._sourceLayer:
            for f in self._geoFields:
                f.setLayer(value)

        self._popLayer = value

    @property
    def joinField(self) -> str:
        return self._joinField or self._geoIdField

    @joinField.setter
    def joinField(self, value: str):
        if value == self._geoIdField or not value:
            self._joinField = None
        else:
            if self.popLayer and self.popLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('join').capitalize(),
                        field=value,
                        layertype=tr('population'),
                        layername=self._popLayer.name()
                    )
                )
            self._joinField = value

    @property
    def popField(self) -> str:
        return self._popField

    @popField.setter
    def popField(self, value: str):
        if value != self._popField:
            if not value:
                raise ValueError(tr('Population field must be set'))
            if self._popLayer and self._popLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('population').capitalize(),
                        field=value,
                        layertype=tr('population'),
                        layername=self._popLayer.name()
                    )
                )

            oldValue = self._popField
            self._popField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'pop-field', value, oldValue)

    @property
    def vapField(self) -> str:
        return self._vapField

    @vapField.setter
    def vapField(self, value: str):
        if value != self._vapField:
            if value and self._popLayer and self._popLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('VAP'),
                        field=value,
                        layertype=tr('population'),
                        layername=self._popLayer.name()
                    )
                )

            oldValue = self._vapField
            self._vapField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'vap-field', value, oldValue)

    @property
    def cvapField(self) -> str:
        return self._cvapField

    @cvapField.setter
    def cvapField(self, value: str):
        if value != self._cvapField:
            if value and self._popLayer and self._popLayer.fields().lookupField(value) == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('CVAP'),
                        field=value,
                        layertype=tr('population'),
                        layername=self._popLayer.name()
                    )
                )

            oldValue = self._cvapField
            self._cvapField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'cvap-field', value, oldValue)

    @property
    def geoDisplay(self) -> str:
        return self._geoDisplay or self._geoIdField

    @geoDisplay.setter
    def geoDisplay(self, value: str):
        if self._geoDisplay != value:
            oldValue = self._geoDisplay
            self._geoDisplay = value
            self.planChanged.emit(self, 'geo-id-display', value, oldValue)

    @property
    def assignLayer(self) -> QgsVectorLayer:
        return self._assignLayer

    def _setAssignLayer(self, value: QgsVectorLayer):
        self._assignLayer = value
        if self._assignLayer is not None:
            self._assignLayer.afterCommitChanges.connect(self.assignmentsCommitted)
            self._group.updateLayers()

            if self._geoIdField is None:
                field = self._assignLayer.fields()[1]
                if field:
                    self._geoIdField = field.name()
            else:
                idx = self._assignLayer.fields().lookupField(self._geoIdField)
                if idx == -1:
                    raise RdsException(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('Geo ID'),
                            field=self._geoIdField,
                            layertype=tr('assignments'),
                            layername=self._assignLayer.name()
                        )
                    )

            if self._distField is None:
                field = self._assignLayer.fields()[-1]
                if field:
                    self._distField = field.name()
            else:
                idx = self._assignLayer.fields().lookupField(self._distField)
                if idx == -1:
                    raise RdsException(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('district').capitalize(),
                            field=self._distField,
                            layertype=tr('assignments'),
                            layername=self._assignLayer.name()
                        )
                    )

    @property
    def distLayer(self) -> QgsVectorLayer:
        return self._distLayer

    def _setDistLayer(self, value: QgsVectorLayer):
        if self._distField:
            idx = value.fields().lookupField(self._distField)
            if idx == -1:
                raise RdsException(
                    tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                        fieldname=tr('district').capitalize(),
                        field=self._distField,
                        layertype=tr('district'),
                        layername=value.name()
                    )
                )
        self._distLayer = value
        self._group.updateLayers()
        self._districts.loadData()

    @property
    def districts(self) -> DistrictList:
        return self._districts

    @districts.setter
    def districts(self, districts: Union[DistrictList, Dict[int, BaseDistrict], List[BaseDistrict]]):
        self.clearError()
        oldDistricts = self._districts[:]
        self._districts.clear()
        if isinstance(districts, list):
            districts = {dist.district: dist for dist in districts}
        self._districts.update(districts)
        self.planChanged.emit(self, 'districts', self._districts[:], oldDistricts)

    @property
    def dataFields(self) -> FieldList:
        return self._dataFields

    @dataFields.setter
    def dataFields(self, value: Union[FieldList, List[DataField]]):
        if self._dataFields == value:
            return

        oldFields = self._dataFields

        newFields: List[DataField] = []
        for f in value:
            if not any(field.field == f.field for field in self._dataFields):
                newFields.append(f)

        removedFields: List[DataField] = []
        for f in self._dataFields:
            if not any(field.field == f.field for field in value):
                removedFields.append(f)

        if isinstance(value, FieldList):
            self._dataFields = value
            self._dataFields.setParent(self)
            for field in self._dataFields:
                field.setParent(self)
        else:
            self._dataFields = FieldList(self, value)

        for f in removedFields:
            self.dataFieldRemoved.emit(self, f)

        if self._distLayer:
            self._addFieldToLayer(
                self._distLayer, [f.makeQgsField() for f in newFields])
        self._districts.updateDistrictFields()
        self._districts.resetData()

        for f in newFields:
            self.dataFieldAdded.emit(self, f)
        self.planChanged.emit(self, 'data-fields', self._dataFields, oldFields)

    @property
    def geoFields(self) -> FieldList:
        return self._geoFields

    @geoFields.setter
    def geoFields(self, value: Union[FieldList, List[Field]]):
        if self._geoFields == value:
            return

        oldFields = self._geoFields

        newFields: List[DataField] = []
        for f in value:
            if not any(field.field == f.field for field in self._geoFields):
                newFields.append(f)

        removedFields: List[DataField] = []
        for f in self._geoFields:
            if not any(field.field == f.field for field in value):
                removedFields.append(f)

        if isinstance(value, FieldList):
            self._geoFields = value
            self._geoFields.setParent(self)
            for field in self._geoFields:
                field.setParent(self._geoFields)
        else:
            self._geoFields = FieldList(self, value)

        for f in removedFields:
            self.geoFieldRemoved.emit(self, f)

        if self._assignLayer:
            self._addFieldToLayer(self._assignLayer, [f.makeQgsField() for f in newFields])

        if newFields:
            self._updateGeoField(newFields)
            for f in newFields:
                self.geoFieldAdded.emit(self, f)
        self.planChanged.emit(self, 'geo-fields', self._geoFields, oldFields)

    @property
    def totalPopulation(self):
        return self._totalPopulation

    @totalPopulation.setter
    def totalPopulation(self, value):
        if value != self._totalPopulation:
            oldValue = value
            self._totalPopulation = value
            self.planChanged.emit(self, 'total-population',
                                  self._totalPopulation, oldValue)

    @property
    def cutEdges(self) -> int:
        return self._cutEdges

    @property
    def ideal(self):
        return round(self._totalPopulation / self.numSeats)

    def devBounds(self, members: int = 1):
        maxDeviation = int(self._totalPopulation *
                           self.deviation / self._numDistricts)
        idealUpper = ceil(members * self._totalPopulation /
                          self.numSeats) + maxDeviation
        idealLower = floor(self._totalPopulation /
                           self.numSeats) - maxDeviation
        return (idealLower, idealUpper)

    @property
    def geoPackagePath(self):
        if self._assignLayer:
            uri = self._assignLayer.dataProvider().dataSourceUri()
            return uri.split('|')[0]

        return ''

    def error(self) -> Union[Tuple[str, int], None]:
        return (self._error, self._errorLevel) if self._error is not None else None

    def setError(self, error, level=Qgis.Warning):
        self._error = error
        self._errorLevel = level
        QgsMessageLog.logMessage(error, 'Redistricting', level)

    def clearError(self):
        self._error = None

    def removeGroup(self):
        self._group.removeGroup()

    def _updateGeoField(self, geoField, progress: QProgressDialog = None):
        def cleanup():
            if progress:
                progress.hide()
                progress.canceled.disconnect(
                    self._updateAssignLayerTask.cancel)
            if self._updateAssignLayerTask.isCanceled():
                self.setError(tr('Add geography field canceled'),
                              Qgis.UserCanceled)
            del self._updateAssignLayerTask

        if not self.assignLayer:
            return None

        if isinstance(geoField, Field):
            geoField = [geoField]

        self._updateAssignLayerTask = AddGeoFieldToAssignmentLayerTask(  # pylint: disable=attribute-defined-outside-init
            self.geoPackagePath,
            self.assignLayer,
            self.sourceLayer,
            geoField,
            self.sourceIdField,
            self.geoIdField
        )
        self._updateAssignLayerTask.taskCompleted.connect(cleanup)
        self._updateAssignLayerTask.taskTerminated.connect(cleanup)
        if progress:
            self._updateAssignLayerTask.progressChanged.connect(
                lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._updateAssignLayerTask.cancel)
        QgsApplication.taskManager().addTask(self._updateAssignLayerTask)
        return self._updateAssignLayerTask

    def _addGeoFieldToAssignLayer(self, geoField: Field, progress: QProgressDialog = None):
        if not self._assignLayer:
            return None

        if not self.sourceLayer:
            return None

        field = geoField.makeQgsField()
        if not field:
            return None

        self._addFieldToLayer(self._assignLayer, field)

        return self._updateGeoField(geoField, progress)

    def createLayers(self, gpkgPath, srcLayer=None, srcGeoIdField=None, progress: QProgressDialog = None):
        def taskCompleted():
            if progress:
                progress.canceled.disconnect(self._createLayersTask.cancel)

            del self._createLayersTask
            self.addLayersFromGeoPackage(gpkgPath)
            self._districts.resetData(updateGeometry=True)
            self.layersCreated.emit(self)

        def taskTerminated():
            if progress:
                progress.hide()
                progress.canceled.disconnect(self._createLayersTask.cancel)
            if self._createLayersTask.isCanceled():
                self.setError(tr('Create layers canceled'), Qgis.UserCanceled)
            elif self._createLayersTask.exception:
                self.setError(
                    tr('Error creating new {} layer: {}').format(
                        tr('assignment'), self._createLayersTask.exception),
                    Qgis.Critical
                )
            del self._createLayersTask

        if not self._name or not self._popLayer or not self._geoIdField or not self._distField or not self._popField:
            self.setError(
                tr('Plan name, source layer, geography id field, and population field must be set '
                    'before creating redistricting plan layers'),
                Qgis.Critical
            )
            return None

        self.clearError()

        self.sourceLayer = srcLayer or self._sourceLayer or self.popLayer
        self.sourceIdField = srcGeoIdField or self._sourceIdField or self.joinField

        self._createLayersTask = CreatePlanLayersTask(  # pylint: disable=attribute-defined-outside-init
            self, gpkgPath, self.sourceLayer, self.sourceIdField)
        self._createLayersTask.taskCompleted.connect(taskCompleted)
        self._createLayersTask.taskTerminated.connect(taskTerminated)
        if progress:
            self._createLayersTask.progressChanged.connect(lambda p: progress.setValue(int(p)))
            progress.canceled.connect(self._createLayersTask.cancel)

        QgsApplication.taskManager().addTask(self._createLayersTask)

        return self._createLayersTask

    def _updateLayerNames(self):
        if self._assignLayer:
            self._assignLayer.setName(f'{self.name}_assignments')
        if self._distLayer:
            self._distLayer.setName(f'{self.name}_districts')

    def addLayersFromGeoPackage(self, gpkgPath):
        self.clearError()

        assignLayer = QgsVectorLayer(
            f'{gpkgPath}|layername=assignments', f'{self.name}_assignments', 'ogr')
        if not assignLayer.isValid():
            self.setError(tr('Error creating new {} layer: {}').format(
                tr('assignment'), assignLayer.lastError()))
            return
        distLayer = QgsVectorLayer(f'{gpkgPath}|layername=districts', f'{self.name}_districts', 'ogr')
        if not distLayer.isValid():
            self.setError(tr('Error creating new {} layer: {}').format(
                tr('district'), distLayer.lastError()))
            return
        QgsProject.instance().addMapLayers([assignLayer, distLayer], False)
        self._setAssignLayer(assignLayer)
        self._setDistLayer(distLayer)

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
            self.setError('Could not add field to layer', Qgis.Critical)
            return
        for field in reversed(fields):
            # ignore fields with conflicting names
            if provider.fields().lookupField(field.name()) != -1:
                fields.remove(field)
        if fields:
            provider.addAttributes(fields)
            layer.updateFields()

    def addDistrict(self, district: int, name='', members=1, description=''):
        self.clearError()
        oldDistricts = self._districts[:]
        dist = self._districts.addDistrict(district, name, members, description)
        self.planChanged.emit(self, 'districts', self._districts[:], oldDistricts)
        return dist

    @overload
    def removeDistrict(self, district: District):
        ...

    @overload
    def removeDistrict(self, district: int):
        ...

    def removeDistrict(self, district):
        self.clearError()

        if isinstance(district, int):
            district = self._districts[str(district)]
        oldDistricts = self._districts[:]
        del self._districts[district.district]
        self.planChanged.emit(
            self, 'districts', self._districts[:], oldDistricts)

    @overload
    def appendDataField(self, field: str, isExpression: bool = False, caption: str = None):
        ...

    @overload
    def appendDataField(self, field: DataField):
        ...

    def appendDataField(self, field, isExpression=False, caption=None):
        self.clearError()

        if isinstance(field, str):
            # don't allow duplicate fields
            if any(f.field == field for f in self._dataFields):
                self.setError(
                    tr('Attempt to add duplicate field {field} to plan {plan}').
                    format(field=field, plan=self.name)
                )
                return

            f = DataField(self.popLayer, field, isExpression, caption)
        elif isinstance(field, DataField):
            if any(f.field == field.field for f in self._dataFields):
                self.setError(
                    tr('Attempt to add duplicate field {field} to plan {plan}').
                    format(field=field.field, plan=self.name))
                return
            f = field
        else:
            raise ValueError(
                tr('Attempt to add invalid field {field!r} to plan {plan}').
                format(field=field, plan=self.name))

        oldDataFields = self._dataFields[:]
        self._dataFields.append(f)

        # add the field to the district layer
        if self._distLayer:
            qf = f.makeQgsField()
            self._addFieldToLayer(self._distLayer, qf)
            self._districts.resetData()

        self._districts.updateDistrictFields()
        self._districts.resetData()
        self.dataFieldAdded.emit(self, f)
        self.planChanged.emit(self, 'data-fields',
                              self._dataFields, oldDataFields)

    @overload
    def removeDataField(self, field: str):
        ...

    @overload
    def removeDataField(self, field: DataField):
        ...

    @overload
    def removeDataField(self, field: int):
        ...

    def removeDataField(self, field):
        self.clearError()

        if isinstance(field, DataField):
            if not field in self._dataFields:
                raise ValueError(
                    tr('Could not remove field {field}. Field not found in plan {plan}.').
                    format(field=field.field, plan=self.name)
                )
        elif isinstance(field, str):
            if field in self._dataFields:
                field = self._dataFields[field]
            else:
                raise ValueError(
                    tr('Could not remove field {field}. Field not found in plan {plan}.').
                    format(field=field, plan=self.name)
                )
        elif isinstance(field, int):
            if 0 <= field < len(self.dataFields):
                field = self._dataFields[field]
            else:
                raise ValueError(tr('Invalid index passed to RedistrictingPlan.removeDataField'))
        else:
            raise ValueError(tr('Invalid index passed to RedistrictingPlan.removeDataField'))

        oldDataFields = self._dataFields[:]
        self._dataFields.remove(field)

        # remove the field from the district table
        if self._distLayer:
            findex = self._distLayer.fields().lookupField(makeFieldName(field))
            if findex != -1:
                provider = self._distLayer.dataProvider()
                provider.deleteAttributes([findex])
                self._distLayer.updateFields()

        self._districts.updateDistrictFields()
        self.dataFieldRemoved.emit(self, field)
        self.planChanged.emit(self, 'data-fields',
                              self._dataFields, oldDataFields)

    @overload
    def appendGeoField(self, field: str, isExpression: bool = False, caption: str = None):
        ...

    @overload
    def appendGeoField(self, field: Field):
        ...

    def appendGeoField(self, field, isExpression=False, caption=None, updateAssignLayer=True):
        self.clearError()

        if isinstance(field, str):
            # don't allow duplicate fields
            if any(f.field == field for f in self._geoFields):
                self.setError(
                    tr('Attempt to add duplicate field {field} to plan {plan}').
                    format(field=field, plan=self.name)
                )
                return

            f = Field(self._sourceLayer or self._popLayer or self._assignLayer,
                      field, isExpression, caption)
        elif isinstance(field, Field):
            if any(f.field == field.field for f in self._geoFields):
                self.setError(
                    tr('Attempt to add duplicate field {field} to plan {plan}').
                    format(field=field.field, plan=self.name)
                )
                return
            f = field
        else:
            raise ValueError(
                tr('Attempt to add invalid field {field!r} to plan {plan}').
                format(field=field, plan=self.name)
            )

        oldGeoFields = self._geoFields[:]
        self._geoFields.append(f)
        if updateAssignLayer and self._assignLayer:
            findex = self._assignLayer.fields().lookupField(f.fieldName)
            if findex == -1:
                self._addGeoFieldToAssignLayer(f)

        self.geoFieldAdded.emit(self, f)
        self.planChanged.emit(self, 'geo-fields', self._geoFields, oldGeoFields)

    @overload
    def removeGeoField(self, field: Field):
        ...

    @overload
    def removeGeoField(self, field: str):
        ...

    @overload
    def removeGeoField(self, field: int):
        ...

    def removeGeoField(self, field):
        self.clearError()

        if isinstance(field, Field):
            if not field in self.geoFields:
                raise ValueError(
                    tr('Could not remove field {field}. Field not found in plan {plan}.').
                    format(field=field.field, plan=self.name)
                )
        elif isinstance(field, str):
            if field in self._geoFields:
                field = self._geoFields[field]
            else:
                raise ValueError(
                    tr('Could not remove field {field}. Field not found in plan {plan}.').
                    format(field=field, plan=self.name)
                )
        elif isinstance(field, int):
            if 0 <= field < len(self.geoFields):
                field = self._geoFields[field]
            else:
                raise ValueError(tr('Invalid index passed to RedistrictingPlan.removeDataField'))
        else:
            raise ValueError(tr('Invalid index passed to RedistrictingPlan.removeDataField'))

        oldGeoFields = self._geoFields[:]
        self._geoFields.remove(field)

        # remove the field from the assignments table
        if self._assignLayer:
            findex = self._assignLayer.fields().lookupField(makeFieldName(field))
            if findex != -1:
                provider = self._assignLayer.dataProvider()
                provider.deleteAttributes([findex])
                self._assignLayer.updateFields()

        self.geoFieldRemoved.emit(self, field)
        self.planChanged.emit(self, 'geo-fields', self._geoFields, oldGeoFields)

    def assignmentsCommitted(self):
        districts = {d.district for d in self._districts if d.delta is not None}
        self._districts.resetData(updateGeometry=True, districts=districts, immediate=True)
