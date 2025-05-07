from collections.abc import Iterable

from qgis.core import (
    QgsFeature,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QVariant

from ..models import (
    DistrictColumns,
    RdsDistrict,
    RdsPlan,
    RdsUnassigned
)


class DistrictReader:
    def __init__(
            self,
            distLayer: QgsVectorLayer,
            distField=DistrictColumns.DISTRICT,
            popField=DistrictColumns.POPULATION,
            columns: list[str] = None
    ):
        if distLayer is None:
            raise ValueError("DistLayer is required to create DistrictReader")

        self._distLayer = distLayer
        self._distField = distField
        self._popField = popField
        if columns is None:
            self._columns = self._distLayer.fields().names()
            if "fid" in self._columns:
                self._columns.remove("fid")
        else:
            self._columns = columns

    def readFromLayer(self) -> list[RdsDistrict]:
        result: list[RdsDistrict] = []

        f: QgsFeature
        for f in self._distLayer.getFeatures():
            data = {
                k: None if isinstance(v, QVariant) and v.isNull() else v
                for k, v in f.attributeMap().items() if k in self._columns
            }

            if self._popField != DistrictColumns.POPULATION and self._popField in data:
                data[DistrictColumns.POPULATION] = data[self._popField]
                del data[self._popField]

            data[DistrictColumns.POPULATION] = data[DistrictColumns.POPULATION] or 0
            if data.get("description", "") is None:
                data["description"] = ""

            if f[str(self._distField)] == 0:
                result.append(RdsUnassigned(fid=f.id(), **data))
            else:
                result.append(RdsDistrict(fid=f.id(), **data))

        return sorted(result, key=lambda s: s.district)

    def loadDistricts(self, plan: RdsPlan):
        plan.blockSignals(True)
        plan.districts.clear()
        for district in self.readFromLayer():
            if district.district == 0:
                plan.districts[0].update(district)
            else:
                plan.addDistrict(district)
        plan.blockSignals(False)


class DistrictWriter:
    def __init__(
            self,
            distLayer: QgsVectorLayer,
            distField=DistrictColumns.DISTRICT,
            popField=DistrictColumns.POPULATION,
            columns: list[str] = None
    ):
        if distLayer is None:
            raise ValueError("DistLayer is required to create DistrictReader")
        self._layer = distLayer
        self._distField = distField
        self._popField = popField
        self._fields = self._layer.fields()
        if columns is not None:
            self._field_map = {
                k: v
                for k, v in map(lambda i, j: (i, j), self._fields.allAttributesList(), self._fields.names())
                if v in columns and v not in [self._distField, "fid"]
            }
        else:
            self._field_map = {
                k: v
                for k, v in map(lambda i, j: (i, j), self._fields.allAttributesList(), self._fields.names())
                if k not in [self._distField, "fid"]
            }
        self._dist_idx = self._fields.indexFromName(self._distField)

    def writeToLayer(self, districts: Iterable[RdsDistrict]):
        def changeAttributes(dist: RdsDistrict, feature: QgsFeature):
            # if all population is assigned, delete the Unassigned feature
            if dist[self._distField] == 0 and not dist[DistrictColumns.POPULATION]:
                if dist.fid != -1:
                    self._layer.deleteFeature(dist.fid)
                return

            dirty = False
            for idx, field in self._field_map.items():
                if field not in dist:
                    continue

                value = dist[field]
                if value != feature[idx]:
                    feature.setAttribute(idx, value)
                    dirty = True

            if dirty:
                if dist.fid == -1:
                    self._layer.addFeature(feat)
                else:
                    self._layer.updateFeature(feat)

        self._layer.startEditing()
        for d in districts:
            if d.fid == -1:
                feat = QgsFeature(self._fields)
                feat.setAttribute(self._dist_idx, d.district)
            else:
                feat = self._layer.getFeature(d.fid)
            changeAttributes(d, feat)
        self._layer.commitChanges(True)
