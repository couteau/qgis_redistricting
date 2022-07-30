# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - background task to create plan layers

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
from __future__ import annotations
from itertools import islice
import sqlite3

from typing import List, TYPE_CHECKING
from contextlib import closing
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    Qgis,
    QgsDataSourceUri,
    QgsMessageLog,
    QgsProject,
    QgsTask,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    QgsVectorLayer,
    QgsVectorFileWriter
)
from qgis.utils import spatialite_connect
from processing.algs.gdal.GdalUtils import GdalUtils
from osgeo import gdal, ogr, osr

from ._exception import CancelledError
from ._debug import debug_thread
from ..utils import tr
from ..Exception import RdsException

if TYPE_CHECKING:
    from .. import RedistrictingPlan, Field, DataField


def getOgrCompatibleSource(input_layer: QgsVectorLayer):
    ogr_data_path = None

    if input_layer is None or input_layer.dataProvider().name() == 'memory':
        pass
    elif input_layer.dataProvider().name() == 'ogr':
        ogr_data_path = \
            GdalUtils.ogrConnectionStringAndFormatFromLayer(input_layer)[0]
    elif input_layer.dataProvider().name() == 'delimitedtext':
        ogr_data_path = GdalUtils.ogrConnectionStringFromLayer(
            input_layer)[7:]
    elif input_layer.dataProvider().name().lower() == 'wfs':
        uri = QgsDataSourceUri(input_layer.source())
        baseUrl = uri.param('url').split('?')[0]
        ogr_data_path = f"WFS:{baseUrl}"
    else:
        ogr_data_path = GdalUtils.ogrConnectionStringFromLayer(
            input_layer)

    return ogr_data_path


def getTableName(layer: QgsVectorLayer, dataset: gdal.Dataset):
    if layer.dataProvider().name() == 'ogr':
        table = GdalUtils.ogrLayerName(layer.dataProvider().dataSourceUri())
    elif dataset.GetLayerCount() == 1:
        table = dataset.GetLayer().GetName()
    else:
        table = layer.name()

    return table


class CreatePlanLayersTask(QgsTask):
    def __init__(self, plan: RedistrictingPlan, gpkgPath, srcLayer: QgsVectorLayer, srcGeoIdField: str):
        super().__init__(tr('Create assignments layer'), QgsTask.AllFlags)
        self.path = gpkgPath
        self.srcLayer = srcLayer
        self.srcGeoIdField = srcGeoIdField

        self.geoIdField = plan.geoIdField
        self.distField = plan.distField
        self.geoFields: List[Field] = list(plan.geoFields)

        self.popLayer = plan.popLayer
        self.dataFields: List[DataField] = list(plan.dataFields)
        self.popField = plan.popField
        self.vapField = plan.vapField
        self.cvapField = plan.cvapField

        self.totalPop = None

        self.exception = None

    def _createDistLayer(self, gpkgPath):
        l = QgsVectorLayer(
            f'MultiPolygon?crs={self.srcLayer.crs().authid()}&index=yes', 'districts', 'memory'
        )
        provider = l.dataProvider()

        fields = [
            QgsField(self.distField, QVariant.Int, 'SMALLINT'),
            QgsField('name', QVariant.String, 'VARCHAR', 127),
            QgsField('members', QVariant.Int, 'SMALLINT'),
            QgsField(self.popLayer.fields().field(self.popField))
        ]
        fieldNames = {self.distField, 'name', 'members', self.popField}
        sql = f'SELECT 0 as {self.distField}, "{tr("Unassigned")}" as name, SUM({self.popField}) as {self.popField}'

        if self.vapField and self.vapField not in fieldNames:
            fields.append(self.popLayer.fields().field(self.vapField))
            fieldNames.add(self.vapField)
            sql += f', SUM({self.vapField}) as {self.vapField}'
        if self.cvapField and self.cvapField not in fieldNames:
            fields.append(self.popLayer.fields().field(self.cvapField))
            fieldNames.add(self.cvapField)
            sql += f', SUM({self.cvapField}) as {self.cvapField}'

        context = None
        for f in self.dataFields:
            if f.fieldName in fieldNames:
                continue

            if f.isExpression:
                context = QgsExpressionContext()
                context.appendScopes(
                    QgsExpressionContextUtils.globalProjectLayerScopes(self.popLayer))
                context.setFeature(next(self.popLayer.getFeatures()))

            qf = f.makeQgsField(context)
            if qf is None:  # pragma: no cover
                continue
            fields.append(qf)
            sql += f', SUM({qf.name()}) as {qf.name()}'

        fields.append(QgsField('polsbypopper', QVariant.Double))
        fields.append(QgsField('reock', QVariant.Double))
        fields.append(QgsField('convexhull', QVariant.Double))

        provider.addAttributes(fields)
        provider.createSpatialIndex()
        l.updateFields()
        l.updateExtents()

        saveOptions = QgsVectorFileWriter.SaveVectorOptions()
        saveOptions.layerName = 'districts'
        saveOptions.layerOptions = ['GEOMETRY_NAME=geometry']
        saveOptions.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        WriteVectorFile = QgsVectorFileWriter.writeAsVectorFormatV3 \
            if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3") \
            else QgsVectorFileWriter.writeAsVectorFormatV2
        error = WriteVectorFile(
            l, gpkgPath, QgsProject.instance().transformContext(), saveOptions
        )

        if error[0] != QgsVectorFileWriter.NoError:
            self.exception = RdsException(
                tr('Error creating new {} layer: {}').format(
                    tr('district'), error[1])
            )
            return False

        f = {}
        source = getOgrCompatibleSource(self.popLayer)
        if source is not None:
            ds: gdal.Dataset = gdal.OpenEx(source, gdal.OF_VECTOR)
            if ds is not None:
                try:
                    sql += f' FROM {getTableName(self.popLayer, ds)}'
                    lyr: ogr.Layer = ds.ExecuteSQL(sql)
                    f = lyr.GetNextFeature().items()
                except:  # pylint: disable=bare-except
                    ...

        if f:
            self.totalPop = f[self.popField]
            with closing(spatialite_connect(gpkgPath)) as db:
                sql = f'INSERT INTO districts ({",".join(f.keys())}) VALUES ({",".join("?" * len(f))})'
                db: sqlite3.Connection
                db.execute(sql, list(f.values()))

        return True

    def qgisTypeToGdalType(self, qt: QVariant.Type):
        if qt == QVariant.String:
            t = ogr.OFTString
        elif qt in (QVariant.Int, QVariant.UInt, QVariant.LongLong, QVariant.ULongLong):
            t = ogr.OFTInteger64
        elif qt == QVariant.Double:
            t = ogr.OFTReal
        else:
            t = ogr.OFTString

        return t

    def run(self):
        debug_thread()

        try:
            if not self._createDistLayer(self.path):
                return False

            ds: gdal.Dataset = gdal.OpenEx(self.path, gdal.OF_UPDATE | gdal.OF_SHARED | gdal.OF_VERBOSE_ERROR, ['GPKG'])
            layer: ogr.Layer = ds.CreateLayer(
                'assignments',
                srs=osr.SpatialReference(self.srcLayer.crs().toWkt()),
                geom_type=ogr.wkbMultiPolygon,
                options=[
                    'GEOMETRY_NAME=geometry',
                    'OVERWRITE=YES',
                    'PRECISION=YES'
                    'FID=fid'
                ]
            )

            fields = []
            srcField = self.srcLayer.fields().field(self.srcGeoIdField)
            t = self.qgisTypeToGdalType(srcField.type())
            fld = ogr.FieldDefn(self.geoIdField, t)
            fld.SetNullable(False)
            fld.SetUnique(True)
            if t == ogr.OFTString:
                fld.SetWidth(srcField.length())
            fields.append(fld)
            fld = ogr.FieldDefn(self.distField, ogr.OFTInteger)
            fld.SetDefault('0')
            fields.append(fld)

            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.srcLayer))
            context.setFeature(next(self.srcLayer.getFeatures()))

            for field in self.geoFields:
                t = self.qgisTypeToGdalType(field.fieldType(context))
                fld = ogr.FieldDefn(field.fieldName, t)
                fields.append(fld)
            layer.CreateFields(fields)
            ds.FlushCache()
            del layer
            del ds

            total = self.srcLayer.featureCount()
            count = 0
            with closing(spatialite_connect(self.path)) as db:
                db: sqlite3.Connection

                db.execute(
                    f'CREATE UNIQUE INDEX idx_districts_{self.distField} ON districts ({self.distField})'
                )
                db.execute(f'CREATE UNIQUE INDEX idx_assignments_{self.geoIdField} ON assignments ({self.geoIdField})')
                db.execute(f'CREATE INDEX idx_assignments_{self.distField} ON assignments ({self.distField})')
                for field in [field.fieldName for field in self.geoFields]:
                    db.execute(f'CREATE INDEX idx_assignments_{field} ON assignments ({field})')
                db.commit()

                gen = (
                    [f[self.srcGeoIdField], 0] +
                    [field.getValue(f, context) for field in self.geoFields] +
                    [f.geometry().asWkt()]
                    for f in self.srcLayer.getFeatures()
                )
                sql = f'INSERT INTO assignments ({",".join(fld.GetName() for fld in fields)}, geometry) ' \
                    f'VALUES({",".join("?" * len(fields))}, GeomFromText(?))'
                while count < total:
                    s = islice(gen, 1000)
                    if self.isCanceled():
                        raise CancelledError()
                    db.executemany(sql, s)
                    count = min(total, count + 1000)
                    self.setProgress(100 * count/total)
                db.commit()

        except CancelledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        self.setProgress(100)
        return True

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(
                    f'{self.exception!r}', 'Redistricting', Qgis.Critical)
