"""QGIS Redistricting Plugin - redistrictin plan model

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
from contextlib import contextmanager
from itertools import repeat
from math import ceil, floor
from typing import Annotated, Optional, Union, cast, overload
from uuid import UUID, uuid4

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import pyqtSignal

from ..utils import tr
from . import consts
from .base import Property, RdsBaseModel, in_range, isidentifier, not_empty, rds_property
from .consts import MAX_DISTRICTS, MIN_DISTRICTS, DeviationType, DistrictColumns, MetricsColumns
from .district import DistrictList, RdsDistrict, RdsUnassigned
from .field import RdsDataField, RdsField, RdsGeoField
from .lists import KeyedList
from .metricslist import RdsMetrics


class RdsPlan(RdsBaseModel):
    nameChanged = pyqtSignal()
    descriptionChanged = pyqtSignal()
    numDistrictsChanged = pyqtSignal()
    numSeatsChanged = pyqtSignal()
    geoIdCaptionChanged = pyqtSignal()
    deviationChanged = pyqtSignal()
    deviationTypeChanged = pyqtSignal()
    popFieldChanged = pyqtSignal()
    popFieldsChanged = pyqtSignal()
    geoFieldsChanged = pyqtSignal()
    dataFieldsChanged = pyqtSignal()
    districtAdded = pyqtSignal("PyQt_PyObject")  # district
    districtRemoved = pyqtSignal("PyQt_PyObject")  # district
    districtDataChanged = pyqtSignal("PyQt_PyObject")  # district
    metricsChanged = pyqtSignal()
    validChanged = pyqtSignal()

    def _validLayer(self, layer: Optional[QgsVectorLayer]) -> Optional[QgsVectorLayer]:
        if layer is not None and not layer.isValid():
            raise ValueError(tr("Value must be a valid vector layer"))

        return layer

    name: Annotated[str, not_empty] = rds_property(type=str, private=True, notify=nameChanged)

    @cast("Property[str]", name).setter
    def name(self, value: str):
        self._name = value
        if self.assignLayer:
            self.assignLayer.setName(f"{self.name}_assignments")

        if self.distLayer:
            self.distLayer.setName(f"{self.name}_districts")

    numDistricts: Annotated[int, in_range(consts.MIN_DISTRICTS, consts.MAX_DISTRICTS)] = rds_property(
        private=True, notify=numDistrictsChanged
    )

    @cast("Property[int]", numDistricts).setter
    def numDistricts(self, value: int):
        if self._numDistricts != value:
            self._numDistricts = value
        if self._numSeats is not None and self._numSeats < self._numDistricts:
            self._numSeats = None

    numSeats: int = None

    @Property(private=True, notify=numSeatsChanged)
    def numSeats(self) -> int:
        return self._numSeats or self.numDistricts

    @numSeats.setter(set_initializer=True)
    def numSeats(self, value: int):
        if value == self.numDistricts:
            self._numSeats = None
        else:
            self._numSeats = value

    @numSeats.validator
    def numSeats(self, value: int):
        if value is not None and value < self.numDistricts:
            raise ValueError(tr("Number of seats must be equal to or greater than number of districts"))

        return value

    deviation: Annotated[float, in_range(0.0)] = rds_property(private=True, default=0.0, notify=deviationChanged)
    deviationType: DeviationType = rds_property(
        private=True, default=DeviationType.OverUnder, notify=deviationTypeChanged
    )

    districts: DistrictList = rds_property(private=True, serialize=False, factory=DistrictList)
    metrics: RdsMetrics = rds_property(private=True, factory=RdsMetrics)

    distField: Annotated[str, isidentifier] = rds_property(private=True, default="district")

    @cast("Property[str]", distField).setter
    def distField(self, value: str):
        with self.checkValid():
            self._renameField(self.assignLayer, self._distField, value)
            self._renameField(self.distLayer, self._distField, value)
            self._distField = value

    geoLayer: Optional[QgsVectorLayer] = rds_property(private=True, fvalid=_validLayer, default=None)

    @cast("Property[QgsVectorLayer]", geoLayer).setter
    def geoLayer(self, value: QgsVectorLayer):
        with self.checkValid():
            if self._geoLayer is not None:
                self._geoLayer.willBeDeleted.disconnect(self.layerDestroyed)
            self._geoLayer = value
            if self._geoLayer:
                self._geoLayer.willBeDeleted.connect(self.layerDestroyed)
                for f in self.geoFields:
                    f.layer = self._geoLayer
                if self._popLayer is None:
                    self._updatePopFieldsLayer(self._geoLayer)

    geoJoinField: Annotated[str, isidentifier] = None

    @Property(private=True)
    def geoJoinField(self) -> str:
        return self._geoJoinField or self._geoIdField

    @geoJoinField.setter
    def geoJoinField(self, value: str):
        if value == self._geoIdField:
            self._geoJoinField = None
        else:
            self._geoJoinField = value

    geoIdField: Annotated[str, isidentifier] = rds_property(private=True, default=None)

    @cast("Property[str]", geoIdField).setter
    def geoIdField(self, value: str):
        with self.checkValid():
            self._renameField(self.assignLayer, self._geoIdField, value)
            self._geoIdField = value

    geoIdCaption: str = None

    @Property(private=True, notify=geoIdCaptionChanged)
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self.geoIdField

    @geoIdCaption.setter(set_initializer=True)
    def geoIdCaption(self, value: str):
        if value == self.geoIdField:
            self._geoIdCaption = None
        else:
            self._geoIdCaption = value

    geoFields: KeyedList[str, RdsGeoField] = rds_property(
        private=True, notify=geoFieldsChanged, factory=KeyedList[str, RdsGeoField]
    )

    popLayer: QgsVectorLayer = None

    @Property(private=True, fvalid=_validLayer)
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer or self._geoLayer

    @popLayer.setter
    def popLayer(self, value: QgsVectorLayer):
        if self._popLayer != value:
            if self._popLayer is not None:
                self._popLayer.willBeDeleted.disconnect(self.layerDestroyed)

            if value == self._geoLayer:
                self._popLayer = None
            else:
                self._popLayer = value
                self._popLayer.willBeDeleted.connect(self.layerDestroyed)

            self._updatePopFieldsLayer(self.popLayer)

    @popLayer.initializer
    def popLayer(self, value: QgsVectorLayer):
        if value == self._geoLayer:
            self._popLayer = None
        else:
            self._popLayer = value
            if self._popLayer is not None:
                self._popLayer.willBeDeleted.connect(self.layerDestroyed)

    popJoinField: Annotated[str, isidentifier] = None

    @Property(private=True)
    def popJoinField(self) -> str:
        return self._popJoinField or self._geoIdField

    @popJoinField.setter
    def popJoinField(self, value: str):
        if value == self._geoIdField:
            self._popJoinField = None
        else:
            self._popJoinField = value

    popField: Annotated[str, isidentifier] = rds_property(private=True, default=None)

    @cast("Property[str]", popField).setter
    def popField(self, value: str):
        with self.checkValid():
            self._popField = value

    popFields: KeyedList[str, RdsField] = rds_property(
        private=True, factory=KeyedList[str, RdsField], notify=popFieldsChanged
    )
    dataFields: KeyedList[str, RdsDataField] = rds_property(
        private=True, factory=KeyedList[str, RdsDataField], notify=dataFieldsChanged
    )

    assignLayer: QgsVectorLayer = None

    distLayer: QgsVectorLayer = None

    description: str = ""

    id: UUID = rds_property(private=True, readonly=True, factory=uuid4)

    def __pre_init__(self):
        self._geoLayer = None
        self._popLayer = None
        self._distField = None
        self._numDistricts = -1

    def __post_init__(self, **kwargs):
        self.districts.append(self.createDistrict(0))
        self.metrics.metricsChanged.connect(self.metricsChanged)

    @property
    def totalPopulation(self) -> int:
        return self.metrics.totalPopulation or 0

    @property
    def idealPopulation(self):
        return round(self.totalPopulation / self.numSeats)

    @property
    def allocatedDistricts(self):
        return len(self.districts) - 1

    @property
    def allocatedSeats(self):
        return sum(d.members for d in self.districts if d.district != 0)  # pylint: disable=not-an-iterable

    @property
    def geoPackagePath(self):
        if self.assignLayer:
            uri = self.assignLayer.dataProvider().dataSourceUri()
            return uri.split("|")[0]

        return ""

    @property
    def districtColumns(self):
        cols = list(DistrictColumns)
        cols.extend(self.popFields.keys())
        cols.extend(self.dataFields.keys())
        cols.extend(list(MetricsColumns))
        return cols

    def createDistrict(self, district: int, name: str = "", members: int = 1, description: str = ""):
        cols = dict(zip(self.districtColumns, repeat(0)))
        cols["description"] = description

        if district == 0:
            del cols[DistrictColumns.DISTRICT]
            del cols[DistrictColumns.NAME]
            del cols[DistrictColumns.MEMBERS]
            del cols[DistrictColumns.DEVIATION]
            del cols[DistrictColumns.PCT_DEVIATION]
            return RdsUnassigned(**cols)

        cols[DistrictColumns.DISTRICT] = district
        cols[DistrictColumns.NAME] = name or str(district)
        cols[DistrictColumns.MEMBERS] = members
        cols[DistrictColumns.DEVIATION] = -self.idealPopulation * members
        cols[DistrictColumns.PCT_DEVIATION] = -1.0

        return RdsDistrict(**cols)

    def districtUpdated(self):
        district = self.sender()
        self.districtDataChanged.emit(district)

    @overload
    def addDistrict(self, district: int, name: str = "", members: int = 1, description: str = "") -> RdsDistrict: ...

    @overload
    def addDistrict(self, district: RdsDistrict) -> RdsDistrict: ...

    def addDistrict(
        self, district: Union[int, RdsDistrict], name: str = "", members: int = 1, description: str = ""
    ) -> RdsDistrict:
        if not isinstance(district, RdsDistrict):
            district = self.createDistrict(district, name, members, description)

        district.nameChanged.connect(self.districtUpdated)
        district.descriptionChanged.connect(self.districtUpdated)
        district.membersChanged.connect(self.districtUpdated)
        self.districts.append(district)
        self.districtAdded.emit(district)
        return district

    def removeDistrict(self, district: Union[RdsDistrict, int]):
        if isinstance(district, int):
            district = self.districts.get(district)
            if district is None:
                return

        if district in self.districts:
            district.nameChanged.disconnect(self.districtUpdated)
            district.descriptionChanged.disconnect(self.districtUpdated)
            district.membersChanged.disconnect(self.districtUpdated)
            self.districts.remove(district)
            self.districtRemoved.emit(district)

    def isValid(self):
        """Test whether plan meets minimum specifications for use"""
        return (
            self.assignLayer is not None
            and self.distLayer is not None
            and self.geoLayer is not None
            and bool(self._name and self._popField and self._geoIdField and self._distField)
            and MIN_DISTRICTS <= self.numDistricts <= MAX_DISTRICTS
        )

    def isDistrictValid(self, district: RdsDistrict):
        maxDeviation = district.members * int(self.totalPopulation * self.deviation / self.numDistricts)
        idealUpper = ceil(district.members * self.totalPopulation / self.numSeats) + maxDeviation
        idealLower = floor(district.members * self.totalPopulation / self.numSeats) - maxDeviation
        return idealLower <= district.population <= idealUpper

    @contextmanager
    def checkValid(self):
        valid = self.isValid()
        try:
            yield valid
        finally:
            if self.isValid() != valid:
                self.validChanged.emit()

    def layerDestroyed(self):
        layer = self.sender()
        if layer == self.assignLayer:
            self._setAssignLayer(None)
        elif layer == self.distLayer:
            self._setDistLayer(None)
        elif layer == self._geoLayer:
            self.geoLayer = None
        elif layer == self._popLayer:
            self.popLayer = None

    def _renameField(self, layer: Optional[QgsVectorLayer], oldName: Optional[str], newName: str):
        if oldName is not None and layer is not None:
            provider = layer.dataProvider()
            idx = provider.fieldNameIndex(oldName)
            if idx != -1 and provider.renameAttributes({idx: newName}):
                layer.updateFields()

    def _updatePopFieldsLayer(self, layer: QgsVectorLayer):
        for f in self.popFields:
            f.layer = layer

    def _setAssignLayer(self, value: QgsVectorLayer):
        with self.checkValid():
            if self.assignLayer is not None:
                self.assignLayer.willBeDeleted.disconnect(self.layerDestroyed)

            self.assignLayer = value

            if self.assignLayer is not None:
                self.assignLayer.willBeDeleted.connect(self.layerDestroyed)

                if self._geoIdField is None:
                    field = self.assignLayer.fields()[1]
                    if field:
                        self._geoIdField = field.name()
                else:
                    idx = self.assignLayer.fields().lookupField(self.geoIdField)
                    if idx == -1:
                        raise ValueError(
                            tr("{fieldname} field {field} not found in {layertype} layer {layername}").format(
                                fieldname=tr("Geo ID"),
                                field=self._geoIdField,
                                layertype=tr("assignments"),
                                layername=self.assignLayer.name(),
                            )
                        )

                if self._distField is None:
                    field = self.assignLayer.fields()[-1]
                    if field:
                        self.distField = field.name()
                else:
                    idx = self.assignLayer.fields().lookupField(self._distField)
                    if idx == -1:
                        raise ValueError(
                            tr("{fieldname} field {field} not found in {layertype} layer {layername}").format(
                                fieldname=tr("district").capitalize(),
                                field=self._distField,
                                layertype=tr("assignments"),
                                layername=self.assignLayer.name(),
                            )
                        )

    def _setDistLayer(self, value: QgsVectorLayer):
        with self.checkValid():
            if self.distLayer is not None:
                self.distLayer.willBeDeleted.disconnect(self.layerDestroyed)

            self.distLayer = value

            if self.distLayer is not None:
                self.distLayer.willBeDeleted.connect(self.layerDestroyed)
                if self._distField:
                    idx = self.distLayer.fields().lookupField(self._distField)
                    if idx == -1:
                        raise ValueError(
                            tr("{fieldname} field {field} not found in {layertype} layer {layername}").format(
                                fieldname=tr("district").capitalize(),
                                field=self._distField,
                                layertype=tr("district"),
                                layername=self.distLayer.name(),
                            )
                        )

    def addLayersFromGeoPackage(self, gpkgPath: Union[str, pathlib.Path]):
        if not pathlib.Path(gpkgPath).resolve().exists():
            raise ValueError(tr("File {gpkgPath} does not exist").format(gpkgPath=str(gpkgPath)))

        assignLayer = QgsVectorLayer(f"{gpkgPath}|layername=assignments", f"{self.name}_assignments", "ogr")
        distLayer = QgsVectorLayer(f"{gpkgPath}|layername=districts", f"{self.name}_districts", "ogr")

        self._setAssignLayer(assignLayer)
        self._setDistLayer(distLayer)
