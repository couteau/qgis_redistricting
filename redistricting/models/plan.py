
import pathlib
from contextlib import contextmanager
from itertools import repeat
from math import (
    ceil,
    floor
)
from typing import (
    Annotated,
    Iterable,
    Optional,
    Union,
    overload
)
from uuid import (
    UUID,
    uuid4
)

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import pyqtSignal

from ..utils import tr
from .base.lists import KeyedList
from .base.model import (
    Factory,
    RdsBaseModel,
    in_range,
    not_empty,
    rds_property
)
from .columns import (
    DistrictColumns,
    MetricsColumns
)
from .district import (
    DistrictList,
    RdsDistrict,
    RdsUnassigned
)
from .field import (
    RdsDataField,
    RdsField,
    RdsGeoField
)
from .metricslist import RdsMetrics
from .validators import DeviationType


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

    def _validLayer(self, layer: Optional[QgsVectorLayer]):
        if layer is not None and not layer.isValid():
            raise ValueError(tr("Value must be a valid vector layer"))

        return layer

    name: Annotated[str, not_empty] = rds_property(private=True, notify=nameChanged)
    numDistricts: Annotated[int, in_range(2, 2000)] = rds_property(private=True, notify=numDistrictsChanged)
    numSeats:  int = None
    deviation: Annotated[float, in_range(0.0)] = rds_property(private=True, default=0.0, notify=deviationChanged)
    deviationType: DeviationType = rds_property(
        private=True, default=DeviationType.OverUnder, notify=deviationTypeChanged
    )

    districts: DistrictList = rds_property(
        private=True, serialize=False, factory=DistrictList
    )
    metrics: RdsMetrics = Factory[RdsMetrics](RdsMetrics)
    totalPopulation: int = 0

    geoLayer: QgsVectorLayer = rds_property(private=True, fvalid=_validLayer, default=None)
    geoJoinField: str = None

    def _setGeoFields(self, geoFields: Iterable[RdsGeoField]):
        self._geoFields.clear()
        self._geoFields.extend(geoFields)
        self.metrics.updateGeoFields(self._geoFields)  # pylint: disable=no-member

    geoFields: KeyedList[RdsGeoField] = rds_property(
        private=True, fset=_setGeoFields, finit=_setGeoFields, notify=geoFieldsChanged, factory=KeyedList
    )

    popLayer: QgsVectorLayer = None
    popJoinField: str = None
    popField: str
    popFields: KeyedList[RdsField] = rds_property(private=True, factory=KeyedList, notify=popFieldsChanged)
    dataFields: KeyedList[RdsDataField] = rds_property(private=True, factory=KeyedList, notify=dataFieldsChanged)

    assignLayer: QgsVectorLayer = None
    geoIdField: str = rds_property(private=True, default=None)
    distField: str = rds_property(private=True, default="district")
    geoIdCaption: str = None

    distLayer: QgsVectorLayer = None

    description: str = ""

    id: UUID = rds_property(private=True, readonly=True, factory=uuid4)

    def __pre_init__(self):
        self._geoLayer = None
        self._popLayer = None
        self._distField = None
        self._geoFields = KeyedList()

    def __post_init__(self, **kwargs):
        self.districts.append(self.createDistrict(0))

        if self.metrics.plan is None:
            self.metrics.plan = self
            self.metrics.updateGeoFields(self.geoFields)  # pylint: disable=no-member

        self.metrics.metricsChanged.connect(self.metricsChanged)  # pylint: disable=no-member

    @name.setter
    def name(self, value: str):
        self._name = value
        if self.assignLayer:
            self.assignLayer.setName(f'{self.name}_assignments')

        if self.distLayer:
            self.distLayer.setName(f'{self.name}_districts')

    @numDistricts.setter
    def numDistricts(self, value: int):
        self._numDistricts = value
        if self._numSeats is not None and self._numSeats < self._numDistricts:
            self._numSeats = None

    @rds_property(private=True, notify=numSeatsChanged)
    def numSeats(self) -> int:
        return self._numSeats or self.numDistricts

    @numSeats.setter
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

    @geoLayer.setter
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

    @rds_property(private=True)
    def geoJoinField(self) -> str:
        return self._geoJoinField or self._geoIdField

    @geoJoinField.setter
    def geoJoinField(self, value: str):
        if value == self._geoIdField:
            self._geoJoinField = None
        else:
            self._geoJoinField = value

    @rds_property(private=True, fvalid=_validLayer)
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

    @rds_property(private=True)
    def popJoinField(self) -> str:
        return self._popJoinField or self._geoIdField

    @popJoinField.setter
    def popJoinField(self, value: str):
        if value == self._geoIdField:
            self._popJoinField = None
        else:
            self._popJoinField = value

    @rds_property(private=True, default=None)
    def popField(self):
        return self._popField

    @popField.setter
    def popField(self, value: str):
        with self.checkValid():
            self._popField = value

    @geoIdField.setter
    def geoIdField(self, value: str):
        with self.checkValid():
            self._renameField(self.assignLayer, self._geoIdField, value)
            self._geoIdField = value

    @distField.setter
    def distField(self, value: str):
        with self.checkValid():
            self._renameField(self.assignLayer, self._distField, value)
            self._renameField(self.distLayer, self._distField, value)
            self._distField = value

    @rds_property(private=True, notify=geoIdCaptionChanged)
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self.geoIdField

    @geoIdCaption.setter
    def geoIdCaption(self, value: str):
        if value == self.geoIdField:
            self._geoIdCaption = None
        else:
            self._geoIdCaption = value

    @property
    def idealPopulation(self):
        return round(self.totalPopulation / self.numSeats)  # pylint: disable=no-member

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
            return uri.split('|')[0]

        return ''

    @property
    def districtColumns(self):
        cols = list(DistrictColumns)
        for f in self.popFields:  # pylint: disable=not-an-iterable
            cols.append(f.fieldName)
        for f in self.dataFields:  # pylint: disable=not-an-iterable
            cols.append(f.fieldName)
        cols.extend(list(MetricsColumns))
        return cols

    def createDistrict(self, district: int, name: str = '', members: int = 1, description: str = ''):
        cols = dict(zip(self.districtColumns, repeat(0)))
        cols['description'] = description

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
    def addDistrict(self, district: int, name: str = '', members: int = 1, description: str = '') -> RdsDistrict:
        ...

    @overload
    def addDistrict(self, district: RdsDistrict) -> RdsDistrict:
        ...

    def addDistrict(self, district: Union[int, RdsDistrict], name: str = '', members: int = 1, description: str = '') -> RdsDistrict:
        if not isinstance(district, RdsDistrict):
            district = self.createDistrict(district, name, members, description)

        district.nameChanged.connect(self.districtUpdated)
        district.descriptionChanged.connect(self.districtUpdated)
        district.membersChanged.connect(self.districtUpdated)
        self.districts.append(district)  # pylint: disable=no-member
        self.districtAdded.emit(district)
        return district

    def removeDistrict(self, district: Union[RdsDistrict, int]):
        if district in self.districts:  # pylint: disable=not-an-iterable, unsupported-membership-test
            district.nameChanged.disconnect(self.districtUpdated)
            district.descriptionChanged.disconnect(self.districtUpdated)
            district.membersChanged.disconnect(self.districtUpdated)
            self.districts.remove(district)  # pylint: disable=no-member
            self.districtRemoved.emit(district)

    def updateMetrics(self, totalPopulation, cutEdges, splitsData):
        if totalPopulation is not None:
            self.totalPopulation = totalPopulation
        self.metrics.updateMetrics(cutEdges, splitsData)  # pylint: disable=no-member

    def isValid(self):
        """Test whether plan meets minimum specifications for use"""
        return self.assignLayer is not None and \
            self.distLayer is not None and \
            self.geoLayer is not None and \
            bool(
                self._name and
                self._popField and
                self._geoIdField and
                self._distField
            ) and 2 <= self.numDistricts <= 2000

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
        for f in self.popFields:  # pylint: disable=not-an-iterable
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
                            tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                                fieldname=tr('Geo ID'),
                                field=self._geoIdField,
                                layertype=tr('assignments'),
                                layername=self.assignLayer.name()
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
                            tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                                fieldname=tr('district').capitalize(),
                                field=self._distField,
                                layertype=tr('assignments'),
                                layername=self.assignLayer.name()
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
                            tr('{fieldname} field {field} not found in {layertype} layer {layername}').format(
                                fieldname=tr('district').capitalize(),
                                field=self._distField,
                                layertype=tr('district'),
                                layername=self.distLayer.name()
                            )
                        )

    def addLayersFromGeoPackage(self, gpkgPath: Union[str, pathlib.Path]):
        if not pathlib.Path(gpkgPath).resolve().exists():
            raise ValueError(tr('File {gpkgPath} does not exist').format(gpkgPath=str(gpkgPath)))

        assignLayer = QgsVectorLayer(f'{gpkgPath}|layername=assignments', f'{self.name}_assignments', 'ogr')
        distLayer = QgsVectorLayer(f'{gpkgPath}|layername=districts', f'{self.name}_districts', 'ogr')

        self._setAssignLayer(assignLayer)
        self._setDistLayer(distLayer)
