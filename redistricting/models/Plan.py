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
from numbers import Number
from typing import (
    Any,
    List,
    Optional,
    Union
)
from uuid import (
    UUID,
    uuid4
)

from qgis.core import (
    QgsProject,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    pyqtSignal
)

from ..exception import RdsException
from ..utils import tr
from .DeltaList import DeltaList
from .District import District
from .DistrictList import DistrictList
from .Field import (
    DataField,
    Field,
    GeoField
)
from .FieldList import FieldList
from .PlanStats import PlanStats


class RedistrictingPlan(QObject):
    nameChanged = pyqtSignal(str)
    descriptionChanged = pyqtSignal(str)
    numDistrictsChanged = pyqtSignal(int)
    numSeatsChanged = pyqtSignal(int)
    geoIdCaptionChanged = pyqtSignal(str)
    deviationChanged = pyqtSignal(float)
    popFieldChanged = pyqtSignal()
    popFieldsChanged = pyqtSignal()
    geoFieldsChanged = pyqtSignal()
    dataFieldsChanged = pyqtSignal()
    districtAdded = pyqtSignal("PyQt_PyObject")  # district
    districtRemoved = pyqtSignal("PyQt_PyObject")  # district
    assignmentsChanged = pyqtSignal("PyQt_PyObject")  # list of changed districts
    validChanged = pyqtSignal()

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
        self._geoFields = FieldList[GeoField]()

        self._distLayer: QgsVectorLayer = None
        self._popField = None
        self._popFields = FieldList[Field]()
        self._dataFields = FieldList[DataField]()

        self._districts = DistrictList(self)
        self._stats = PlanStats(self)
        self._delta = DeltaList(self)

        self._updateDistricts = set()

        QgsProject.instance().layerWillBeRemoved.connect(self.layerRemoved)

    def __copy__(self):
        data = self.serialize()
        del data['id']
        if 'assign-layer' in data:
            del data['assign-layer']
        if 'dist-layer' in data:
            del data['dist-layer']
        return RedistrictingPlan.deserialize(data)

    def __deepcopy__(self, memo):
        return self.__copy__()

    def serialize(self) -> dict[str, Any]:
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

            'plan-stats': self._stats.serialize()
        }

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def deserialize(cls, data: dict[str, Any], parent: Optional[QObject] = None):
        uuid = data.get('id')
        uuid = UUID(uuid) if uuid else uuid4()
        name = data.get('name', str(uuid))
        numDistricts = data.get('num-districts')

        plan = cls(name, numDistricts, uuid, parent)

        plan._description = data.get('description', '')
        plan._numSeats = data.get('num-seats')
        plan._totalPopulation = data.get('total-population', 0)
        plan._deviation = data.get('deviation', 0.0)

        plan._distField = data.get('dist-field', plan._distField)
        plan._geoIdField = data.get('geo-id-field')
        plan._geoIdCaption = data.get('geo-id-caption', '')

        if 'geo-layer' in data:
            geoLayer = QgsProject.instance().mapLayer(data['geo-layer'])
            plan._setGeoLayer(geoLayer)

        plan._geoJoinField = data.get('geo-join-field')

        if 'pop-layer' in data:
            popLayer = QgsProject.instance().mapLayer(data.get('pop-layer'))
            plan._popLayer = popLayer
        plan._popJoinField = data.get('pop-join-field', '')
        plan._popField = data.get('pop-field')

        for field in data.get('pop-fields', []):
            f = Field.deserialize(field)
            if f:
                plan._popFields.append(f)

        for field in data.get('data-fields', []):
            f = DataField.deserialize(field)
            if f:
                plan._dataFields.append(f)

        for field in data.get('geo-fields', []):
            f = GeoField.deserialize(field)
            if f:
                plan._geoFields.append(f)

        plan._stats = PlanStats.deserialize(data.get('plan-stats', {}), plan)

        plan._setAssignLayer(QgsProject.instance().mapLayer(data.get('assign-layer')))
        plan._setDistLayer(QgsProject.instance().mapLayer(data.get('dist-layer')))

        return plan

    def isValid(self):
        """Test whether plan meets minimum specifications for use"""
        return bool(
            self.name and
            self.assignLayer and
            self.distLayer and
            self.geoLayer and
            self.geoIdField and
            self.popField and
            self.distField and
            self.numDistricts >= 2
        )

    def isComplete(self):
        # all districts allocated and all seats allocated and no unallocated population
        return self.isValid() and \
            self.allocatedDistricts == self.numDistricts and \
            self.allocatedSeats == self.numSeats and \
            self._districts[0].population == 0

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
            self._name = value
            self.nameChanged.emit(self._name)
            self._updateLayerNames()

    @property
    def numDistricts(self) -> int:
        return self._numDistricts

    def _setNumDistricts(self, value: int):
        if self._numDistricts != value:
            self._numDistricts = value
            self.numDistrictsChanged.emit(self._numDistricts)

    @property
    def numSeats(self) -> int:
        return self._numSeats or self._numDistricts

    def _setNumSeats(self, value: int):
        if (self._numSeats is None and value != self._numDistricts) \
                or (value is None and self.numSeats != self._numDistricts):
            if value == self._numDistricts:
                self._numSeats = None
            else:
                self._numSeats = value
            self.numSeatsChanged.emit(self.numSeats)

    @property
    def allocatedDistricts(self):
        return len(self._districts) - 1

    @property
    def allocatedSeats(self):
        return sum(d.members for d in self._districts)

    @property
    def description(self) -> str:
        return self._description

    def _setDescription(self, value: str):
        if self._description != value:
            self._description = value
            self.descriptionChanged.emit(self._description)

    @property
    def deviation(self) -> float:
        return self._deviation

    def _setDeviation(self, value: Number):
        if self._deviation != value:
            self._deviation = float(value)
            self.deviationChanged.emit(self._deviation)

    @property
    def geoIdField(self) -> str:
        return self._geoIdField

    @property
    def distField(self) -> str:
        return self._distField or 'district'

    @property
    def geoLayer(self) -> QgsVectorLayer:
        return self._geoLayer

    def _setGeoLayer(self, value: QgsVectorLayer):
        if not isinstance(value, QgsVectorLayer) or not value.isValid():
            raise ValueError(tr("Geography layer must be a valid vector layer"))

        if self._geoLayer != value:
            self._geoLayer = value
            for f in self._geoFields:
                f.setLayer(self._geoLayer)

            if self._popLayer is None:
                self.updatePopFields(self._geoLayer)

    @ property
    def geoJoinField(self) -> str:
        return self._geoJoinField or self._geoIdField

    @property
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer or self._geoLayer

    def _setPopLayer(self, value: QgsVectorLayer):
        if not isinstance(value, QgsVectorLayer) or not value.isValid():
            raise ValueError("Population layer must be a valid vector layer")

        if self.popLayer != value:
            if value == self._geoLayer:
                self._popLayer = None

            self.updatePopFields(self.popLayer)

    def updatePopFields(self, layer: QgsVectorLayer):
        for f in self._popFields:
            f.setLayer(layer)
        for f in self._dataFields:
            f.setLayer(layer)

    @property
    def popJoinField(self) -> str:
        return self._popJoinField or self._geoIdField

    def _setPopJoinField(self, value: str):
        if (self._popJoinField is None and value != self._geoIdField) \
                or (value is None and self.popJoinField != self._geoIdField):
            if value == self._geoIdField:
                self._popJoinField = None
            else:
                self._popJoinField = value

    @property
    def popField(self) -> str:
        return self._popField

    def _setPopField(self, value: str):
        if value != self._popField:
            self._popField = value
            self.popFieldChanged.emit()

    @property
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self._geoIdField

    def _setGeoIdCaption(self, value: str):
        if (self._geoIdCaption is None and value != self._geoIdField) \
                or (value is None and self.geoIdCaption != self._geoIdField):
            if value == self._geoIdField:
                self._geoIdCaption = None
            else:
                self._geoIdCaption = value
            self.geoIdCaptionChanged.emit(self.geoIdCaption)

    @property
    def assignLayer(self) -> QgsVectorLayer:
        return self._assignLayer

    def _setAssignLayer(self, value: QgsVectorLayer):
        self._assignLayer = value

        if self._assignLayer is not None:
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

            self._assignLayer.beforeCommitChanges.connect(self.checkForChangedAssignments)
            self._assignLayer.afterCommitChanges.connect(self.signalChangedAssignments)
            self._assignLayer.afterRollBack.connect(self.clearChangedAssignments)

    def checkForChangedAssignments(self):
        dindex = self._assignLayer.fields().lookupField(self._distField)
        if dindex == -1:
            return

        new = {}
        changedAttrs: dict[int, dict[int, Any]] = self._assignLayer.editBuffer().changedAttributeValues()
        for fid, attrs in changedAttrs.items():
            for fld, value in attrs.items():
                if fld == dindex:
                    new[fid] = value

        old = {
            f[dindex] for f in self._assignLayer.dataProvider().getFeatures(list(new.keys()))
        }
        self._updateDistricts = set(new.values()) | old

    def clearChangedAssignments(self):
        self._updateDistricts = set()

    def signalChangedAssignments(self):
        self.assignmentsChanged(self._updateDistricts)
        self._updateDistricts = set()

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

    @property
    def popFields(self) -> FieldList[Field]:
        return self._popFields

    def _setPopFields(self, value: Union[FieldList, List[Field]]):
        if self._popFields == value:
            return
        self._popFields.clear()
        self._popFields.extend(value)
        self.popFieldsChanged.emit()

    @property
    def dataFields(self) -> FieldList[DataField]:
        return self._dataFields

    def _setDataFields(self, value: Union[FieldList, List[DataField]]):
        if self._dataFields == value:
            return

        self._dataFields.clear()
        self._dataFields.extend(value)
        self.dataFieldsChanged.emit()

    @property
    def geoFields(self) -> FieldList[GeoField]:
        return self._geoFields

    def _setGeoFields(self, value: Union[FieldList[GeoField], List[GeoField]]):
        if self._geoFields == value:
            return

        self._geoFields.clear()
        self._geoFields.extend(value)
        self.geoFieldsChanged.emit()

    @property
    def totalPopulation(self):
        return self._totalPopulation

    @property
    def ideal(self):
        return round(self._totalPopulation / self.numSeats)

    @property
    def districts(self) -> DistrictList:
        return self._districts

    def addDistrict(self, district: District):
        self._districts.append(district)
        self.districtAdded.emit(district)

    def removeDistrict(self, district: District):
        if district in self._districts:
            self._districts.remove(district)
            self.districtRemoved.emit(district)

    @property
    def delta(self):
        return self._delta

    @property
    def stats(self) -> PlanStats:
        return self._stats

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

    def layerRemoved(self, layer):
        valid = self.isValid()

        if layer == self._assignLayer:
            self._setAssignLayer(None)
        elif layer == self._distLayer:
            self._setDistLayer(None)
        elif layer == self._popLayer:
            self._popLayer = None
        elif layer == self._geoLayer:
            self._geoLayer = None

        if self.isValid() != valid:
            self.validChanged.emit()

    def _updateLayerNames(self):
        if self._assignLayer:
            self._assignLayer.setName(f'{self.name}_assignments')
        if self._distLayer:
            self._distLayer.setName(f'{self.name}_districts')

    def addLayersFromGeoPackage(self, gpkgPath: Union[str, pathlib.Path]):
        if not pathlib.Path(gpkgPath).resolve().exists():
            raise ValueError(tr('File {gpkgPath} does not exist').format(gpkgPath=str(gpkgPath)))

        assignLayer = QgsVectorLayer(f'{gpkgPath}|layername=assignments', f'{self.name}_assignments', 'ogr')
        distLayer = QgsVectorLayer(f'{gpkgPath}|layername=districts', f'{self.name}_districts', 'ogr')

        self._setAssignLayer(assignLayer)
        self._setDistLayer(distLayer)

    def updateTotalPopulation(self, totalPopulation: int):
        self._totalPopulation = totalPopulation
