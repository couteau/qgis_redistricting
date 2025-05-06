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

import pathlib
from sqlite3 import DatabaseError
from typing import TYPE_CHECKING, Union

import geopandas as gpd
import pandas as pd
from qgis.core import Qgis, QgsMessageLog, QgsTask, QgsVectorLayer
from qgis.PyQt.QtCore import QMetaType

from ...errors import CanceledError
from ...utils import spatialite_connect, tr
from ._debug import debug_thread

if TYPE_CHECKING:
    from ...models import RdsPlan


class ImportAssignmentFileTask(QgsTask):
    def __init__(  # noqa: PLR0913
        self,
        plan: RdsPlan,
        equivalencyFile: Union[str, pathlib.Path],
        headerRow=True,
        geoColumn=0,
        distColumn=1,
        delimiter=",",
        quotechar='"',
        joinField=None,
    ):
        super().__init__(tr("Import assignment file"), QgsTask.AllFlags)

        self.assignLayer: QgsVectorLayer = plan.assignLayer
        self.setDependentLayers((self.assignLayer,))

        self.distField: str = plan.distField
        self.geoIdField: str = plan.geoIdField
        self.geoPackagePath: str = plan.geoPackagePath
        self.equivalencyFile = pathlib.Path(equivalencyFile) if isinstance(equivalencyFile, str) else equivalencyFile
        self.headerRow = headerRow
        self.geoColumn = geoColumn
        self.distColumn = distColumn
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.joinField = self.geoIdField if joinField is None else joinField
        self.exception: Exception = None

    def run(self) -> bool:
        def updateProgress(iterator):
            nonlocal progress
            for tup in iterator:
                if self.isCanceled():
                    raise CanceledError()

                progress += 1
                self.setProgress(100 * progress / total)
                yield tup

        debug_thread()

        fGeo = self.assignLayer.fields()[self.geoIdField]
        geoType = str if fGeo.type() == QMetaType.Type.QString else int
        fDist = self.assignLayer.fields()[self.distField]
        distType = str if fDist.type() == QMetaType.Type.QString else int

        converters = {self.geoColumn: geoType, self.distColumn: distType}

        if not self.equivalencyFile.exists():
            self.exception = FileNotFoundError(f"File {self.equivalencyFile} does not exist")
            return False

        if self.equivalencyFile.suffix in (".xls", ".xlsx", ".xlsm", ".ods"):
            assignments = pd.read_excel(
                self.equivalencyFile,
                header=0 if self.headerRow else None,
                usecols=(self.geoColumn, self.distColumn),
                converters=converters,
            )
        elif self.equivalencyFile.suffix in (".csv", ".txt"):
            try:
                assignments = pd.read_csv(
                    self.equivalencyFile,
                    header=0 if self.headerRow else None,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                    skipinitialspace=True,
                    usecols=(self.geoColumn, self.distColumn),
                    converters=converters,
                )
            except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as e:
                self.exception = e
                return False
        elif self.equivalencyFile.suffix == ".shp":
            assignments = gpd.read_file(self.equivalencyFile, columns=(self.geoColumn, self.distColumn))
        else:
            self.exception = ValueError(tr("Unsupported file type for import"))
            return False

        try:
            total = len(assignments)
            progress = 0

            with spatialite_connect(self.geoPackagePath) as db:
                sql = f'UPDATE assignments SET "{self.distField}" = ? WHERE "{self.joinField}" == ?'  # noqa: S608

                db.executemany(sql, updateProgress(assignments.itertuples(index=False)))
                db.commit()
        except CanceledError:
            return False
        except DatabaseError as e:
            self.exception = e
            return False

        return True

    def finished(self, result: bool):
        if result:
            self.assignLayer.reload()
        elif self.exception:
            QgsMessageLog.logMessage(f"{self.exception!r}", "Redistricting", Qgis.MessageLevel.Critical)
