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
    Dict,
    List,
    Optional,
    Union
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

from .DeltaList import DeltaList
from .DistrictList import DistrictList
from .ErrorList import ErrorListMixin
from .Exception import RdsException
from .Field import (
    DataField,
    Field,
    GeoField
)
from .FieldList import FieldList
from .PlanAssignments import PlanAssignmentEditor
from .PlanGroup import PlanGroup
from .PlanStats import PlanStats
from .PlanUpdate import PlanUpdater
from .utils import tr


class RedistrictingPlan(ErrorListMixin, QObject):
    planChanged = pyqtSignal('PyQt_PyObject', 'PyQt_PyObject')
    districtsUpdating = pyqtSignal('PyQt_PyObject')
    districtsUpdated = pyqtSignal('PyQt_PyObject')
    districtUpdateTerminated = pyqtSignal(bool)

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
        self._geoFields = FieldList[GeoField]()

        self._distLayer: QgsVectorLayer = None
        self._popField = None
        self._popFields = FieldList[Field]()
        self._dataFields = FieldList[DataField]()

        self._districts = DistrictList(self)
        self._stats = PlanStats(self)
        self._delta = DeltaList(self)
        self._updater = PlanUpdater(self)
        self._updater.updateStarted.connect(self.districtsUpdating)
        self._updater.updateComplete.connect(self.districtsUpdated)
        self._updater.updateTerminated.connect(self.districtUpdateTerminated)

        self._updating = 0
        self._oldvalues: dict[str, Any] = None

        self._assignmentEditor: PlanAssignmentEditor = None

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

        plan._districts.updateDistrictFields()
        plan._stats = PlanStats.deserialize(data.get('plan-stats', {}), plan)

        plan._setAssignLayer(QgsProject.instance().mapLayer(data.get('assign-layer')))
        plan._setDistLayer(QgsProject.instance().mapLayer(data.get('dist-layer')))

        return plan

    def startPlanUpdate(self):
        if self._updating == 0:
            self._oldvalues = self.serialize()
        self._updating += 1

    def endPlanUpdate(self):
        if self._updating == 0:
            return

        self._updating -= 1
        if self._updating == 0:
            startUpdate = False
            newvalues = self.serialize()
            modifiedFields = {
                k for k in newvalues if k not in self._oldvalues or newvalues[k] != self._oldvalues[k]
            }
            modifiedFields |= {k for k in self._oldvalues if k not in newvalues}
            self._oldvalues = None

            if "name" in modifiedFields:
                self._updateLayerNames()
                self._group.updateName()

            if "num-districts" in modifiedFields:
                self._districts.updateNumDistricts()

            if "geo-fields" in modifiedFields:
                self._stats.updateGeoFields()
                self._updater.updateSplits()
                startUpdate = True

            if modifiedFields & {"pop-layer", "pop-field", "pop-fields", "data-fields"}:
                self._districts.updateDistrictFields()
                self._updater.updateDemographics()
                startUpdate = True

            self.planChanged.emit(self, modifiedFields)

            if startUpdate:
                self._updater.startUpdate()

    def cancelPlanUpdate(self):
        if self._updating > 0:
            self._name = self._oldvalues.get('name')
            self._description = self._oldvalues.get('description', '')
            self._numDistricts = self._oldvalues.get('num-districts')
            self._numSeats = self._oldvalues.get('num-seats')
            self._deviation = self._oldvalues.get('deviation', 0.0)

            self._totalPopulation = self._oldvalues.get('total-population', 0)

            self._geoIdCaption = self._oldvalues.get('geo-id-caption', '')

            if 'pop-layer' in self._oldvalues:
                popLayer = QgsProject.instance().mapLayer(self._oldvalues.get('pop-layer'))
                self._popLayer = popLayer
            self._popJoinField = self._oldvalues.get('pop-join-field', '')
            self._popField = self._oldvalues.get('pop-field')

            self._popFields.clear()
            for field in self._oldvalues.get('pop-fields', []):
                f = Field.deserialize(field)
                if f:
                    self._popFields.append(f)

            self._dataFields.clear()
            for field in self._oldvalues.get('data-fields', []):
                f = DataField.deserialize(field)
                if f:
                    self._dataFields.append(f)

            self._geoFields.clear()
            for field in self._oldvalues.get('geo-fields', []):
                f = GeoField.deserialize(field)
                if f:
                    self._geoFields.append(f)

        self._oldvalues = None
        self._updating = 0

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
            self.startPlanUpdate()
            self._name = value
            self.endPlanUpdate()

    @property
    def numDistricts(self) -> int:
        return self._numDistricts

    def _setNumDistricts(self, value: int):
        if self._numDistricts != value:
            self.startPlanUpdate()
            self._numDistricts = value
            self.endPlanUpdate()

    @property
    def numSeats(self) -> int:
        return self._numSeats or self._numDistricts

    def _setNumSeats(self, value: int):
        if (self._numSeats is None and value != self._numDistricts) \
                or (value is None and self.numSeats != self._numDistricts):
            self.startPlanUpdate()
            if value == self._numDistricts:
                self._numSeats = None
            else:
                self._numSeats = value
            self.endPlanUpdate()

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
            self.startPlanUpdate()
            self._description = value
            self.endPlanUpdate()

    @property
    def deviation(self) -> float:
        return self._deviation

    def _setDeviation(self, value: Number):
        if self._deviation != value:
            self.startPlanUpdate()
            self._deviation = float(value)
            self.endPlanUpdate()

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
            raise ValueError("Geographer layer must be a valid vector layer")

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
            self.startPlanUpdate()
            if value == self._geoIdField:
                self._popJoinField = None
            else:
                self._popJoinField = value
            self.endPlanUpdate()

    @property
    def popField(self) -> str:
        return self._popField

    def _setPopField(self, value: str):
        if value != self._popField:
            self.startPlanUpdate()
            self._popField = value
            self.endPlanUpdate()

    @property
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self._geoIdField

    def _setGeoIdCaption(self, value: str):
        if (self._geoIdCaption is None and value != self._geoIdField) \
                or (value is None and self.geoIdCaption != self._geoIdField):
            self.startPlanUpdate()
            if value == self._geoIdField:
                self._geoIdCaption = None
            else:
                self._geoIdCaption = value
            self.endPlanUpdate()

    @property
    def assignLayer(self) -> QgsVectorLayer:
        return self._assignLayer

    def _setAssignLayer(self, value: QgsVectorLayer):
        self._assignLayer = value
        self._delta.setAssignLayer(value)
        self._updater.setAssignLayer(value)
        self.stopEditing()

        if self._assignLayer is not None:
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
    def popFields(self) -> FieldList[Field]:
        return self._popFields

    def _setPopFields(self, value: Union[FieldList, List[Field]]):
        if self._popFields == value:
            return
        self.startPlanUpdate()
        self._popFields.clear()
        self._popFields.extend(value)
        self.endPlanUpdate()

    @property
    def dataFields(self) -> FieldList[DataField]:
        return self._dataFields

    def _setDataFields(self, value: Union[FieldList, List[DataField]]):
        if self._dataFields == value:
            return

        self.startPlanUpdate()
        self._dataFields.clear()
        self._dataFields.extend(value)
        self.endPlanUpdate()

    @property
    def geoFields(self) -> FieldList[GeoField]:
        return self._geoFields

    def _setGeoFields(self, value: Union[FieldList[GeoField], List[GeoField]]):
        if self._geoFields == value:
            return

        self.startPlanUpdate()
        self._geoFields.clear()
        self._geoFields.extend(value)
        self.endPlanUpdate()

    @property
    def totalPopulation(self):
        return self._totalPopulation

    @totalPopulation.setter
    def totalPopulation(self, value):
        if value != self._totalPopulation:
            self.startPlanUpdate()
            self._totalPopulation = value
            self.endPlanUpdate()

    @property
    def ideal(self):
        return round(self._totalPopulation / self.numSeats)

    @property
    def districts(self) -> DistrictList:
        return self._districts

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

    def removeGroup(self):
        self._group.removeGroup()

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

    def startEditing(self):
        if self._assignmentEditor is None:
            self._assignmentEditor = PlanAssignmentEditor(self, self)

        return self._assignmentEditor

    def stopEditing(self):
        self._assignmentEditor = None

    def updateDistricts(self, updateGeometry=True):
        if updateGeometry:
            self._updater.updateDistricts(immediate=True)
        else:
            self._updater.updateDemographics(immediate=True)

    def updateTotalPopulation(self, totalPopulation: int):
        self._totalPopulation = totalPopulation

    def updateDistrictData(self, data):
        self._districts.setData(data)

    def updateStatsData(self, cutEdges, splits):
        self._stats.setData(cutEdges, splits)
