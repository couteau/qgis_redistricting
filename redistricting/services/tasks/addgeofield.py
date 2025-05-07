"""QGIS Redistricting Plugin - background task to add a new geofield

        begin                : 2022-06-01
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

from typing import TYPE_CHECKING, List

from qgis.core import (
    Qgis,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsTask,
    QgsVectorLayer,
)
from qgis.utils import spatialite_connect

from ...utils import tr
from ...utils.misc import quote_identifier
from ._debug import debug_thread

if TYPE_CHECKING:
    from ...models import RdsField


class AddGeoFieldToAssignmentLayerTask(QgsTask):
    def __init__(  # noqa: PLR0913
        self,
        geoPackagePath: str,
        assignLayer: QgsVectorLayer,
        srcLayer: QgsVectorLayer,
        geoFields: List["RdsField"],
        srcIdField: str,
        geoIdField: str,
    ):
        super().__init__(tr("Add geography field to assignment layer"), QgsTask.Flag.AllFlags)
        self.geoPackagePath = geoPackagePath
        self.assignLayer = assignLayer
        self.srcLayer = srcLayer
        self.geoFields = geoFields
        self.srcIdField = srcIdField
        self.geoIdField = geoIdField
        self.exception = None

    def run(self):
        def makeGetter(field: "RdsField"):
            if not field.isExpression():
                findex = self.srcLayer.fields().lookupField(field.field)
                if findex == -1:
                    raise RuntimeError(
                        tr("Could not find {field} in {source} layer").format(field=field.field, source=tr("source"))
                    )

                return lambda f: f[findex]
            else:
                return lambda f: field.getValue(f, context)

        debug_thread()

        try:
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.srcLayer))

            gindex = self.srcLayer.fields().lookupField(self.srcIdField)
            if gindex == -1:
                self.exception = RuntimeError(
                    tr("Could not find {field} in {source} layer").format(field=self.srcIdField, source=tr("source"))
                )
                return False

            getters = [makeGetter(geoField) for geoField in self.geoFields]
            getters.append(lambda f: f[gindex])
            request = QgsFeatureRequest()
            request.setFlags(QgsFeatureRequest.NoGeometry)

            with spatialite_connect(self.geoPackagePath) as db:
                params = ",".join(geoField.fieldName + " = ?" for geoField in self.geoFields)
                sql = f"UPDATE assignments SET {params} WHERE {quote_identifier(self.geoIdField)} = ?"  # noqa: S608
                chunk = []
                chunkSize = 1000
                total = self.srcLayer.featureCount() or 1
                count = 0

                for f in self.srcLayer.getFeatures(request):
                    chunk.append([getter(f) for getter in getters])
                    if len(chunk) == chunkSize:
                        db.executemany(sql, chunk)
                        count += chunkSize
                        self.setProgress(100 * count / total)
                        chunk = []

                if len(chunk) > 0:
                    db.executemany(sql, chunk)
                    chunk = []
                db.commit()

            self.setProgress(100)
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True

    def finished(self, result: bool):
        if not result:
            if self.exception is not None:
                QgsMessageLog.logMessage(f"{self.exception!r}", "Redistricting", Qgis.MessageLevel.Critical)
        else:
            self.assignLayer.reload()
