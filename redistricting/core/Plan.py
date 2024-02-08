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
import pathlib
from math import (
    ceil,
    floor
)
from numbers import Number
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Union,
    overload
)
from uuid import (
    UUID,
    uuid4
)

from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from .District import (
    BaseDistrict,
    District
)
from .DistrictList import DistrictList
from .ErrorList import ErrorListMixin
from .Exception import RdsException
from .Field import (
    DataField,
    Field,
    GeoField
)
from .FieldList import FieldList
from .PlanGroup import PlanGroup
from .PlanStats import PlanStatistics
from .utils import tr


class RedistrictingPlan(ErrorListMixin, QObject):
    popFieldAdded = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    popFieldRemoved = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
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

        self._geoLayer = None
        self._geoJoinField = None

        self._popLayer: QgsVectorLayer = None
        self._popJoinField = None

        self._assignLayer: QgsVectorLayer = None
        self._geoIdField = None
        self._geoIdCaption = None
        self._distField = 'district'
        self._geoFields = FieldList[GeoField](self)

        self._distLayer: QgsVectorLayer = None
        self._popField = None
        self._popFields = FieldList[Field](self)
        self._dataFields = FieldList[DataField](self)

        self._districts = DistrictList(self)
        self._stats = PlanStatistics(self)

        QgsProject.instance().layerWillBeRemoved.connect(self.layerRemoved)

    def __copy__(self):
        data = self.serialize()
        del data['id']
        if 'assign-layer' in data:
            del data['assign-layer']
        if 'dist-layer' in data:
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
            'pop-join-field': self._popJoinField,

            'geo-layer': self._geoLayer.id() if self._geoLayer else None,
            'geo-join-field': self._geoJoinField,

            'assign-layer': self._assignLayer.id() if self._assignLayer else None,
            'geo-id-field': self._geoIdField,
            'geo-id-caption': self._geoIdCaption,
            'dist-field': self._distField,
            'geo-fields': [field.serialize() for field in self._geoFields],

            'dist-layer': self._distLayer.id() if self._distLayer else None,
            'pop-field': self._popField,
            'pop-fields': [field.serialize() for field in self._popFields],
            'data-fields': [field.serialize() for field in self._dataFields],

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
        plan._geoIdCaption = data.get('geo-id-caption', '')

        popLayer = QgsProject.instance().mapLayer(data.get('pop-layer'))
        plan._popJoinField = data.get('pop-join-field', '')
        plan._popField = data.get('pop-field')
        plan._setPopLayer(popLayer)
        for field in data.get('pop-fields', []):
            f = Field.deserialize(field, plan.popFields)
            if f:
                plan._popFields.append(f)

        for field in data.get('data-fields', []):
            f = DataField.deserialize(field, plan.dataFields)
            if f:
                plan._dataFields.append(f)

        plan._districts.updateDistrictFields()

        for field in data.get('geo-fields', []):
            f = GeoField.deserialize(field, plan.geoFields)
            if f:
                plan._geoFields.append(f)

        for dist in data.get('districts', []):
            plan._districts.deserializeDistrict(dist)

        plan._setAssignLayer(QgsProject.instance().mapLayer(data.get('assign-layer')))
        plan._setDistLayer(QgsProject.instance().mapLayer(data.get('dist-layer')))
        if 'geo-layer' in data:
            layer = QgsProject.instance().mapLayer(data['geo-layer'])
            plan._geoLayer = layer

        plan._geoJoinField = data.get('geo-join-field')

        plan._stats = PlanStatistics.deserialize(plan, data.get('plan-stats', {}))
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
            if value < oldValue:
                for i in range(value + 1, oldValue):
                    del self._districts[str(i)]
            self._numDistricts = value
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
    def geoLayer(self) -> QgsVectorLayer:
        return self._geoLayer or self._popLayer

    def _setGeoLayer(self, value: QgsVectorLayer):
        if self.geoLayer != value or (value is None and self.geoLayer != self._popLayer):
            if value == self._popLayer:
                self._geoLayer = None
            else:
                self._geoLayer = value

            for f in self._geoFields:
                f.setLayer(self.geoLayer)

    @ property
    def geoJoinField(self) -> str:
        return self._geoJoinField or self._geoIdField

    def _setGeoJoinField(self, value: str):
        if (self._geoJoinField is None and value != self._geoIdField) \
                or (value is None and self.geoJoinField != self._geoIdField):
            oldValue = self.geoJoinField
            if value == self._geoIdField:
                self._geoJoinField = None
            else:
                self._geoJoinField = value
            self.planChanged.emit(self, 'src-id-field', self.geoJoinField, oldValue)

    @property
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer

    def _setPopLayer(self, value: QgsVectorLayer):

        if self._popLayer != value:
            for f in self._popFields:
                f.setLayer(self._popLayer)
            for f in self._dataFields:
                f.setLayer(self._popLayer)

            syncGeoLayer = self._geoLayer is None
            if syncGeoLayer:
                self._setGeoLayer(value)

            self._popLayer = value

            if syncGeoLayer:
                self._geoLayer = None

            self._districts.resetData()

    @property
    def popJoinField(self) -> str:
        return self._popJoinField or self._geoIdField

    def _setPopJoinField(self, value: str):
        if (self._popJoinField is None and value != self._geoIdField) \
                or (value is None and self.popJoinField != self._geoIdField):
            oldValue = self.popJoinField
            if value == self._geoIdField:
                self._popJoinField = None
            else:
                self._popJoinField = value
            self.planChanged.emit(self, 'join-field', self.popJoinField, oldValue)

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
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self._geoIdField

    def _setGeoIdCaption(self, value: str):
        if (self._geoIdCaption is None and value != self._geoIdField) \
                or (value is None and self.geoIdCaption != self._geoIdField):
            oldValue = self.geoIdCaption
            if value == self._geoIdField:
                self._geoIdCaption = None
            else:
                self._geoIdCaption = value

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
    def popFields(self) -> FieldList[Field]:
        return self._popFields

    def _setPopFields(self, value: Union[FieldList, List[Field]]):
        if self._popFields == value:
            return

        oldFields = self._popFields

        newFields: Set[Field] = set(value) - set(oldFields)
        removedFields: Set[Field] = set(oldFields) - set(value)

        self._popFields.clear()
        self._popFields.extend(value)

        self._districts.updateDistrictFields()
        self._districts.resetData()

        for f in removedFields:
            self.popFieldRemoved.emit(self, f)

        for f in newFields:
            self.popFieldAdded.emit(self, f)

        self.planChanged.emit(self, 'pop-fields', self._popFields, oldFields)

    @property
    def dataFields(self) -> FieldList[DataField]:
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

    def _setGeoFields(self, value: Union[FieldList[GeoField], List[GeoField]]):
        if self._geoFields == value:
            return

        oldFields = self._geoFields

        newFields: Set[GeoField] = set(value) - set(oldFields)
        removedFields: Set[GeoField] = set(oldFields) - set(value)

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
    def stats(self) -> PlanStatistics:
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
        elif self._geoLayer:
            self._geoLayer = None

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
