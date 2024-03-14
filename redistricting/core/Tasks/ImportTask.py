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

import csv
import os
from contextlib import closing
from typing import TYPE_CHECKING

from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer
)
from qgis.utils import spatialite_connect

from ..Exception import CanceledError
from ..utils import tr
from ._debug import debug_thread

if TYPE_CHECKING:
    from .. import RedistrictingPlan


class ImportAssignmentFileTask(QgsTask):
    def __init__(
            self,
            plan: RedistrictingPlan,
            equivalencyFile,
            headerRow=True,
            geoColumn=0,
            distColumn=1,
            delimiter=',',
            quotechar='"',
            joinField=None
    ):
        super().__init__(tr('Import assignment file'), QgsTask.AllFlags)

        self.assignLayer: QgsVectorLayer = plan._assignLayer
        self.setDependentLayers((self.assignLayer,))

        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.geoPackagePath: str = plan.geoPackagePath
        self.equivalencyFile = equivalencyFile
        self.headerRow = headerRow
        self.geoColumn = geoColumn
        self.distColumn = distColumn
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.joinField = self.geoIdField if joinField is None else joinField
        self.exception: Exception = None

    def run(self) -> bool:
        def makeTuple(tup):
            nonlocal progress
            if self.isCanceled():
                raise CanceledError()

            progress += 1
            self.setProgress(100*progress/total)
            return tup

        debug_thread()

        oldHeaders = False
        csvfile = None
        try:
            total = 1
            progress = 0

            if not os.path.exists(self.equivalencyFile):
                return False

            _, ext = os.path.splitext(self.equivalencyFile)
            if ext in ('.xls', '.xlsx', '.xlsm', '.ods'):
                headerConfigKey = 'OGR_XLS_HEADERS' if ext == '.xls' \
                    else 'OGR_XLSX_HEADERS' if ext in ('.xlsx', '.xlsm') \
                    else 'OGR_ODS_HEADERS'
                oldHeaders = gdal.GetConfigOption(headerConfigKey)
                gdal.SetConfigOption(headerConfigKey, 'FORCE' if self.headerRow else 'DISABLE')
                l = QgsVectorLayer(str(self.equivalencyFile), '__import', 'ogr')
                total = l.featureCount()
                generator = (makeTuple((f[self.distColumn], f[self.geoColumn])) for f in l.getFeatures())
            elif ext in ('.csv', '.txt'):
                with open(self.equivalencyFile, encoding='utf-8-sig') as f:
                    total = sum(1 for l in f) or 1

                csvfile = open(self.equivalencyFile,  # pylint: disable=consider-using-with
                               newline='',
                               encoding='utf-8-sig')
                dialect = csv.Sniffer().sniff(csvfile.read(1024))
                if self.delimiter is not None:
                    dialect.delimiter = self.delimiter
                if self.quotechar is not None:
                    dialect.quotechar = self.quotechar
                dialect.skipinitialspace = True
                csvfile.seek(0)
                dist = csv.reader(csvfile, dialect=dialect)
                if self.headerRow:
                    next(dist)

                generator = (makeTuple((l[self.distColumn], l[self.geoColumn])) for l in dist)
            else:
                self.exception = ValueError(tr('Unsupported file type for import'))
                return False

            with closing(spatialite_connect(self.geoPackagePath)) as db:
                sql = f"UPDATE assignments SET {self.distField} = ? WHERE {self.joinField} == ?"

                db.executemany(sql, generator)
                db.commit()
        except CanceledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False
        finally:
            if csvfile:
                csvfile.close()
            if oldHeaders is not False and self.headerRow:
                gdal.SetConfigOption(headerConfigKey, oldHeaders)

        self.setProgress(100)
        return True

    def finished(self, result: bool):
        if result:
            self.assignLayer.reload()
        elif self.exception:
            QgsMessageLog.logMessage(
                f'{self.exception!r}', 'Redistricting', Qgis.Critical
            )
