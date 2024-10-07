from typing import Iterable

from qgis.core import (
    QgsFeature,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import QVariant

from ..models import (
    District,
    DistrictColumns,
    RedistrictingPlan,
    Unassigned
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

    def readFromLayer(self) -> list[District]:
        result: list[District] = []

        f: QgsFeature
        for f in self._distLayer.getFeatures():
            data = {
                k: None if isinstance(v, QVariant) and v.isNull() else v
                for k, v in f.attributeMap().items() if k in self._columns
            }

            if self._popField != DistrictColumns.POPULATION and self._popField in data:
                data[DistrictColumns.POPULATION] = data[self._popField]
                del data[self._popField]

            if f[self._distField] == 0:
                result.append(Unassigned(fid=f.id(), **data))
            else:
                result.append(District(fid=f.id(), **data))

        return sorted(result, key=lambda s: s.district)

    def loadDistricts(self, plan: RedistrictingPlan):
        plan.districts.clear()
        for district in self.readFromLayer():
            if district.district == 0:
                plan.districts[0].update(district)
            else:
                plan.districts.add(district)


class DistrictWriter:
    def __init__(
            self,
            distLayer: QgsVectorLayer,
            distField=DistrictColumns,
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

    def writeToLayer(self, districts: Iterable[District]):
        def changeAttributes(dist: District, feature: QgsFeature):

            # if all population is assigned, delete the Unassigned feature
            if dist[self._distField] == 0 and not dist[DistrictColumns.POPULATION]:
                if dist.fid != -1:
                    self._layer.deleteFeature(dist.fid)
                return

            for idx, field in self._field_map.items():
                if field not in dist:
                    continue

                value = dist[field]
                if value != feature[idx]:
                    feature.setAttribute(idx, value)

            if dist.fid == -1:
                self._layer.addFeature(feat)
            else:
                self._layer.updateFeature(feat)

        self._layer.startEditing()
        for d in districts:
            if d.fid == -1:
                feat = QgsFeature(self._fields)
                feat.setAttribute(DistrictColumns.DISTRICT, d.district)
            else:
                feat = self._layer.getFeature(d.fid)
            changeAttributes(d, feat)
        self._layer.commitChanges(True)
