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

from typing import TYPE_CHECKING

from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsMessageLog,
    QgsProject,
    QgsSpatialIndex,
    QgsTask,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import NULL

from ..Exception import CanceledError
from ..utils import tr
from ._debug import debug_thread

if TYPE_CHECKING:
    from .. import RedistrictingPlan


class ImportShapeFileTask(QgsTask):
    def __init__(
        self,
        plan: RedistrictingPlan,
        shapeFile,
        importDistField
    ):
        super().__init__(tr('Import districts from shapefile'), QgsTask.AllFlags)
        self.assignLayer = plan._assignLayer
        self.distField = plan.distField
        self.shapeFile = shapeFile
        self.importDistField = importDistField
        self.exception = None
        self.errors = []

    def makeProjection(self, layer: QgsVectorLayer):
        crsSrc = layer.crs()
        crsDest = self.assignLayer.crs()
        if crsSrc.authid() != crsDest.authid():
            transformContext = QgsProject.instance().transformContext()
            xform = QgsCoordinateTransform(crsSrc, crsDest, transformContext)
            l = QgsVectorLayer(f"multipolygon?crs={crsDest}", "xformlayer",  "memory")
            pv = l.dataProvider()
            pv.addAttributes(layer.fields().toList())
            l.updateFields()
            feats = []
            for f in layer.getFeatures():
                g = QgsGeometry(f.geometry())
                g.transform(xform)
                f.setGeometry(g)
                feats.append(f)

            pv.addFeatures(feats)
            l.updateExtents()
            return l

        return layer

    def run(self):
        debug_thread()
        try:
            layer = QgsVectorLayer(self.shapeFile)
            sindex = layer.fields().lookupField(self.importDistField)
            if sindex == -1:
                self.exception = ValueError('invalid source field for shapefile import')
                return False
            dindex = self.assignLayer.fields().lookupField(self.distField)
            if dindex == -1:
                self.exception = ValueError('invalid district field for shapefile import')
                return False

            layer = self.makeProjection(layer)
            index = QgsSpatialIndex(layer.getFeatures())

            distmap = {}
            d: QgsFeature
            for d in layer.getFeatures():
                dist = d[sindex]
                if dist == NULL:
                    dist = 0
                elif isinstance(dist, str) and dist.isnumeric():
                    dist = int(dist)
                elif not isinstance(dist, int):
                    dist = d.id()+1
                distmap[d[sindex]] = dist

            total = self.assignLayer.featureCount()
            count = 0
            f: QgsFeature
            self.assignLayer.startEditing()
            for f in self.assignLayer.getFeatures():
                g: QgsGeometry = f.geometry()
                for d in layer.getFeatures(index.intersects(g.boundingBox())):
                    i = g.intersection(d.geometry())
                    if not i.isEmpty() and i.area() > g.area() / 2:
                        self.assignLayer.changeAttributeValue(f.id(), dindex, distmap[d[sindex]])
                        break
                else:
                    self.errors.append(f.id())

                count += 1
                if self.isCanceled():
                    raise CanceledError()
                self.setProgress(100*count/total)
            self.assignLayer.commitChanges(True)

        except CanceledError:
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.exception = e
            return False

        return True

    def finished(self, result: bool):
        if result:
            self.assignLayer.reload()
        elif self.exception:
            QgsMessageLog.logMessage(
                f'{self.exception!r}', 'Redistricting', Qgis.Critical
            )
