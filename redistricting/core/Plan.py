# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - core redistricting plan logic

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
import pathlib
from typing import Any, Dict, Set, List, Optional, Union, overload
from math import ceil, floor
from uuid import UUID, uuid4

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import Qgis, QgsProject, QgsVectorLayer

from .Exception import RdsException
from .ErrorList import ErrorListMixin
from .FieldList import FieldList
from .Field import Field, DataField
from .DistrictList import DistrictList
from .District import BaseDistrict, District
from .PlanGroup import PlanGroup
from .utils import tr
from .PlanStats import PlanStats


class RedistrictingPlan(ErrorListMixin, QObject):
    dataFieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    dataFieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    geoFieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    geoFieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    planChanged = pyqtSignal('PyQt_PyObject', str, 'PyQt_PyObject', 'PyQt_PyObject')

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
        self._geoDisplay = None
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
        self._stats = PlanStats(self)

        QgsProject.instance().layerWillBeRemoved.connect(self.layerRemoved)

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
            'pop-layer': self._popLayer.id() if self._popLayer else None,
            'assign-layer': self._assignLayer.id() if self._assignLayer else None,
            'dist-layer': self._distLayer.id() if self._distLayer else None,
            'geo-id-field': self._geoIdField,
            'geo-id-display': self._geoDisplay,
            'dist-field': self._distField,
            'join-field': self._joinField,
            'pop-field': self._popField,
            'vap-field': self._vapField,
            'cvap-field': self._cvapField,
            'src-layer': self._sourceLayer.id() if self._sourceLayer else None,
            'src-id-field': self._sourceIdField,
            'data-fields': [field.serialize() for field in self._dataFields],
            'geo-fields': [field.serialize() for field in self._geoFields],
            'districts': [dist.serialize() for dist in self._districts if dist.district != 0],
            'plan-stats': self._stats.serialize()
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
        plan._numSeats = data.get('num-seats')
        plan._deviation = data.get('deviation', 0.0)

        plan._totalPopulation = data.get('total-population', 0)

        plan._distField = data.get('dist-field', plan._distField)
        plan._geoIdField = data.get('geo-id-field')
        plan._geoDisplay = data.get('geo-id-display', '')

        plan._joinField = data.get('join-field')
        plan._popField = data.get('pop-field')
        plan._vapField = data.get('vap-field')
        plan._cvapField = data.get('cvap-field')
        plan._setPopLayer(QgsProject.instance().mapLayer(data.get('pop-layer')))

        for field in data.get('data-fields', []):
            f = DataField.deserialize(field, plan.dataFields)
            if f:
                plan._dataFields.append(f)

        plan._districts.updateDistrictFields()

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

        plan._stats = PlanStats.deserialize(plan, data.get('plan-stats', {}))
        if plan._totalPopulation == 0:
            plan._districts.resetData()

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

    def _setName(self, value: str):
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

    def _setNumDistricts(self, value: int):
        if self._numDistricts != value:
            oldValue = self._numDistricts
            if self._numDistricts < oldValue:
                for i in range(value + 1, oldValue):
                    del self._districts[str(i)]
            self._numDistricts = self._numDistricts
            self.planChanged.emit(self, 'num-districts', self._numDistricts, oldValue)

    @property
    def numSeats(self) -> int:
        return self._numSeats or self._numDistricts

    def _setNumSeats(self, value: int):
        if (self._numSeats is None and value != self._numDistricts) \
                or (value is None and self.numSeats != self._numDistricts):
            oldValue = self.numSeats
            if value == self._numDistricts:
                self._numSeats = None
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

    def _setDescription(self, value: str):
        if self._description != value:
            oldValue = self._description
            self._description = value
            self.planChanged.emit(self, 'description', self._description, oldValue)

    @property
    def deviation(self) -> float:
        return self._deviation

    def _setDeviation(self, value: Number):
        if self._deviation != value:
            oldValue = self._deviation
            self._deviation = float(value)
            self.planChanged.emit(self, 'deviation', self._deviation, oldValue)

    @property
    def geoIdField(self) -> str:
        return self._geoIdField

    def _setGeoIdField(self, value: str):
        if self._geoIdField != value:
            oldValue = self._geoIdField
            self._geoIdField = value
            self._districts.resetData(updateGeometry=True)
            self.planChanged.emit(self, 'geo-id-Field', self._geoIdField, oldValue)

    @property
    def distField(self) -> str:
        return self._distField or 'district'

    def _setDistField(self, value: str):
        if self._distField != value:
            oldValue = self._distField
            self._distField = value
            self._districts.resetData(updateGeometry=True)
            self.planChanged.emit('dist-field', self._distField, oldValue)

    @property
    def sourceLayer(self) -> QgsVectorLayer:
        return self._sourceLayer or self._popLayer

    def _setSourceLayer(self, value: QgsVectorLayer):
        if self.sourceLayer != value or (value is None and self.sourceLayer != self._popLayer):
            if value == self._popLayer:
                self._sourceLayer = None
            else:
                self._sourceLayer = value

            for f in self._geoFields:
                f.setLayer(self.sourceLayer)

    @ property
    def sourceIdField(self) -> str:
        return self._sourceIdField or self._geoIdField

    def _setSourceIdField(self, value: str):
        if (self._sourceIdField is None and value != self._geoIdField) \
                or (value is None and self.sourceIdField != self._geoIdField):
            oldValue = self.sourceIdField
            if value == self._geoIdField:
                self._sourceIdField = None
            else:
                self._sourceIdField = value
            self.planChanged.emit(self, 'src-id-field', self.sourceIdField, oldValue)

    @property
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer

    def _setPopLayer(self, value: QgsVectorLayer):
        if self._popLayer != value:
            for f in self._dataFields:
                f.setLayer(self._popLayer)

            syncSrcLayer = self._sourceLayer is None
            if syncSrcLayer:
                self._setSourceLayer(value)

            self._popLayer = value

            if syncSrcLayer:
                self._sourceLayer = None

            self._districts.resetData()

    @property
    def joinField(self) -> str:
        return self._joinField or self._geoIdField

    def _setJoinField(self, value: str):
        if (self._joinField is None and value != self._geoIdField) \
                or (value is None and self.joinField != self._geoIdField):
            oldValue = self.joinField
            if value == self._geoIdField:
                self._joinField = None
            else:
                self._joinField = value
            self.planChanged.emit(self, 'join-field', self.joinField, oldValue)

    @property
    def popField(self) -> str:
        return self._popField

    def _setPopField(self, value: str):
        if value != self._popField:
            oldValue = self._popField
            self._popField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'pop-field', value, oldValue)

    @property
    def vapField(self) -> str:
        return self._vapField

    def _setVAPField(self, value: str):
        if value != self._vapField:
            oldValue = self._vapField
            self._vapField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'vap-field', value, oldValue)

    @property
    def cvapField(self) -> str:
        return self._cvapField

    def _setCVAPField(self, value: str):
        if value != self._cvapField:
            oldValue = self._cvapField
            self._cvapField = value
            self._districts.updateDistrictFields()
            self._districts.resetData()
            self.planChanged.emit(self, 'cvap-field', value, oldValue)

    @property
    def geoDisplay(self) -> str:
        return self._geoDisplay or self._geoIdField

    def _setGeoDisplay(self, value: str):
        if (self._geoDisplay is None and value != self._geoIdField) \
                or (value is None and self.geoDisplay != self._geoIdField):
            oldValue = self.geoDisplay
            if value == self._geoIdField:
                self._geoDisplay = None
            else:
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
        self._distLayer = value
        if self._distLayer is not None:
            if self._distField:
                idx = self._distLayer.fields().lookupField(self._distField)
                if idx == -1:
                    raise RdsException(
                        tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                            fieldname=tr('district').capitalize(),
                            field=self._distField,
                            layertype=tr('district'),
                            layername=self._distLayer.name()
                        )
                    )
            self._group.updateLayers()
            self._districts.loadData()

    @property
    def districts(self) -> DistrictList:
        return self._districts

    @districts.setter
    def districts(self, districts: Union[DistrictList, Dict[int, BaseDistrict], List[BaseDistrict]]):
        self.clearErrors()
        oldDistricts = self._districts[:]
        self._districts.clear()
        if isinstance(districts, list):
            districts = {dist.district: dist for dist in districts}
        self._districts.update(districts)
        self.planChanged.emit(self, 'districts', self._districts[:], oldDistricts)

    @property
    def dataFields(self) -> FieldList:
        return self._dataFields

    def _setDataFields(self, value: Union[FieldList, List[DataField]]):
        if self._dataFields == value:
            return

        oldFields = self._dataFields

        newFields: Set[DataField] = set(value) - set(oldFields)
        removedFields: Set[DataField] = set(oldFields) - set(value)

        self._dataFields.clear()
        self._dataFields.extend(value)

        self._districts.updateDistrictFields()
        self._districts.resetData()

        for f in removedFields:
            self.dataFieldRemoved.emit(self, f)

        for f in newFields:
            self.dataFieldAdded.emit(self, f)

        self.planChanged.emit(self, 'data-fields', self._dataFields, oldFields)

    @property
    def geoFields(self) -> FieldList:
        return self._geoFields

    def _setGeoFields(self, value: Union[FieldList, List[Field]]):
        if self._geoFields == value:
            return

        oldFields = self._geoFields

        newFields: Set[Field] = set(value) - set(oldFields)
        removedFields: Set[Field] = set(oldFields) - set(value)

        self._geoFields.clear()
        self._geoFields.extend(value)

        for f in removedFields:
            self.geoFieldRemoved.emit(self, f)

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
    def stats(self) -> PlanStats:
        return self._stats

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

    def validatePopField(self, field: str, fieldname: str, layer: QgsVectorLayer = None):
        if layer is None:
            layer = self._popLayer

        if not layer:
            return True

        if (idx := layer.fields().lookupField(field)) == -1:
            raise RdsException(
                tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                    fieldname=fieldname,
                    field=field,
                    layertype=tr('population'),
                    layername=layer.name()
                )
            )

        f = layer.fields().field(idx)
        if not f.isNumeric():
            raise RdsException(
                tr('{fieldname} field {field} must be numeric').format(
                    fieldname=fieldname,
                    field=field
                )
            )

        return True

    def removeGroup(self):
        self._group.removeGroup()

    def resetData(self, updateGeometry=False, districts: set[int] = None, immediate=False):
        self._districts.resetData(updateGeometry, districts, immediate)

    def updateDistricts(self, force=False):
        return self._districts.updateDistricts(force)

    def layerRemoved(self, layer):
        if layer == self._assignLayer:
            self._setAssignLayer(None)
        elif layer == self._distLayer:
            self._setDistLayer(None)
        elif layer == self._popLayer:
            self._popLayer = None
        elif self._sourceLayer:
            self._sourceLayer = None

    def _updateLayerNames(self):
        if self._assignLayer:
            self._assignLayer.setName(f'{self.name}_assignments')
        if self._distLayer:
            self._distLayer.setName(f'{self.name}_districts')

    def addLayersFromGeoPackage(self, gpkgPath: Union[str, pathlib.Path]):
        self.clearErrors()
        if not pathlib.Path(gpkgPath).resolve().exists():
            self.setError(f'File {gpkgPath} does not exist', Qgis.Critical)
            return

        assignLayer = QgsVectorLayer(
            f'{gpkgPath}|layername=assignments', f'{self.name}_assignments', 'ogr')
        if not assignLayer.isValid():
            self.setError(tr('Error creating new {} layer: {}').format(
                tr('assignment'), assignLayer.lastError()), Qgis.Critical)
            return

        distLayer = QgsVectorLayer(f'{gpkgPath}|layername=districts', f'{self.name}_districts', 'ogr')
        if not distLayer.isValid():
            self.setError(tr('Error creating new {} layer: {}').format(
                tr('district'), distLayer.lastError()), Qgis.Critical)
            return

        QgsProject.instance().addMapLayers([assignLayer, distLayer], False)
        self._setAssignLayer(assignLayer)
        self._setDistLayer(distLayer)

    def addDistrict(self, district: int, name='', members=1, description=''):
        self.clearErrors()
        oldDistricts = self._districts[:]
        dist = self._districts.addDistrict(district, name, members, description)
        self.planChanged.emit(self, 'districts', self._districts[:], oldDistricts)
        return dist

    @ overload
    def removeDistrict(self, district: District):
        ...

    @ overload
    def removeDistrict(self, district: int):
        ...

    def removeDistrict(self, district):
        self.clearErrors()

        if isinstance(district, int):
            district = self._districts[str(district)]
        oldDistricts = self._districts[:]
        del self._districts[district.district]
        self.planChanged.emit(
            self, 'districts', self._districts[:], oldDistricts)

    def assignmentsCommitted(self):
        districts = {d.district for d in self._districts if d.delta is not None}
        self._districts.resetData(updateGeometry=True, districts=districts, immediate=True)
