
import pathlib
import re
from contextlib import contextmanager
from typing import (
    Annotated,
    Optional,
    Union,
    overload
)
from uuid import (
    UUID,
    uuid4
)

from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QObject,
    QVariant,
    pyqtSignal
)
from qgis.PyQt.QtGui import QIcon

from ..utils import tr
from .base import (
    Factory,
    ListFactory,
    RdsBaseModel
)
from .prop import (
    MISSING,
    in_range,
    not_empty,
    rds_property
)


class RdsSplits:
    def __init__(self, field: RdsGeoField):
        self.field = field
        self.splits = {}


class RdsPlanStats(QObject):
    totalPopulation: int
    cutEdges: int
    splits: dict

    def updateGeoFields(self, geoFields: list[RdsGeoField]):
        splits = {}
        for f in geoFields:
            splits[f.field] = RdsSplits(f)
        self.splits = splits


class RdsPlan(RdsBaseModel):
    validChanged = pyqtSignal()

    def _validLayer(self, layer: Optional[QgsVectorLayer]):
        if layer is not None and not layer.isValid():
            raise ValueError(tr("Value must be a valid vector layer"))

        return layer

    name: Annotated[str, not_empty] = rds_property(private=True, strict=True)
    numDistricts: Annotated[int, in_range(2, 2000)] = rds_property(private=True, strict=True)
    numSeats:  int = None

    districts: list = ListFactory
    stats: RdsPlanStats = Factory[RdsPlanStats](RdsPlanStats)

    geoLayer: QgsVectorLayer = rds_property(private=True, fvalid=_validLayer, default=None)
    geoJoinField: str = None
    geoFields: list[RdsGeoField] = rds_property(private=True, factory=ListFactory)

    popLayer: QgsVectorLayer = None
    popJoinField: str = None
    popField: str = rds_property(private=True, default=None)
    popFields: list[RdsField] = ListFactory
    dataFields: list[RdsDataField] = ListFactory

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
        self._geoIdField = None
        self._distField = None

    @name.setter
    def name(self, value: str):
        self._name = value
        if self.assignLayer:
            self.assignLayer.setName(f'{self.name}_assignments')

        if self.distLayer:
            self.distLayer.setName(f'{self.name}_districts')

    @rds_property(private=True)
    def numSeats(self) -> int:
        return self._numSeats or self.numDistricts

    @numSeats.validator
    def numSeats(self, value: int):
        if value is not None and value < self.numDistricts:
            raise ValueError(tr("Number of seats must be equal to or greater than number of districts"))

        return value

    @numSeats.setter
    def numSeats(self, value: int):
        if value == self.numDistricts:
            self._numSeats = None
        else:
            self._numSeats = value

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

    @geoFields.setter
    def geoFields(self, geoFields: list[RdsGeoField]):
        self._geoFields = geoFields
        self.stats.updateGeoFields(self._geoFields)  # pylint: disable=no-member

    @rds_property(fvalid=_validLayer)
    def popLayer(self) -> QgsVectorLayer:
        return self._popLayer or self._geoLayer

    @popLayer.setter
    def popLayer(self, value: QgsVectorLayer):
        if self.popLayer != value:
            if self._popLayer is not None:
                self._popLayer.willBeDeleted.disconnect(self.layerDestroyed)

            if value == self._geoLayer:
                self._popLayer = None
            else:
                self._popLayer = value
                self._popLayer.willBeDeleted.connect(self.layerDestroyed)

            self._updatePopFieldsLayer(self.popLayer)

    @rds_property(private=True)
    def popJoinField(self) -> str:
        return self._popJoinField or self._geoIdField

    @popJoinField.setter
    def popJoinField(self, value: str):
        if value == self._geoIdField:
            self._popJoinField = None
        else:
            self._popJoinField = value

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

    @rds_property(private=True)
    def geoIdCaption(self) -> str:
        return self._geoIdCaption or self.geoIdField

    @geoIdCaption.setter
    def geoIdCaption(self, value: str):
        if value == self.geoIdField:
            self._geoIdCaption = None
        else:
            self._geoIdCaption = value

    @property
    def totalPopulation(self):
        return self.stats.totalPopulation  # pylint: disable=no-member

    @property
    def idealPopulation(self):
        return round(self.stats.totalPopulation / self.numSeats)  # pylint: disable=no-member

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

    @overload
    def addDistrict(self, district: int, name: str = '', members: int = 1, description: str = '') -> District:
        ...

    @overload
    def addDistrict(self, district: District) -> District:
        ...

    def addDistrict(self, district: Union[int, District], name: str = '', members: int = 1, description: str = '') -> District:
        if not isinstance(district, District):
            cols = dict(zip(self.districtColumns, repeat(0)))
            cols[DistrictColumns.DISTRICT] = district
            cols[DistrictColumns.NAME] = name
            cols[DistrictColumns.MEMBERS] = members
            cols[DistrictColumns.DEVIATION] = -self.ideal * members
            cols[DistrictColumns.PCT_DEVIATION] = -1.0
            cols['description'] = description
            district = District(**cols)

        self._districts.add(district)
        self.districtAdded.emit(district)
        return district

    def removeDistrict(self, district: Union[District, int]):
        if district in self._districts:
            self._districts.remove(district)
            self.districtRemoved.emit(district)
        else:
            QgsMessageLog.logMessage

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
