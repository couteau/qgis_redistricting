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
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from qgis.core import (
    Qgis,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
    QgsSpatialIndex,
    QgsTask,
    QgsVectorLayer
)

from ._exception import CancelledError
from ._debug import debug_thread
from ..Utils import tr

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
        self.assignLayer = plan.assignLayer
        self.distField = plan.distField
        self.shapeFile = shapeFile
        self.importDistField = importDistField
        self.exception = None
        self.errors = []

    def run(self):
        debug_thread()
        try:
            layer = QgsVectorLayer(self.shapeFile)

            crsSrc = layer.crs()
            crsDest = self.assignLayer.crs()
            if crsSrc.authid() != crsDest.authid():
                transformContext = QgsProject.instance().transformContext()
                xform = QgsCoordinateTransform(crsSrc, crsDest, transformContext)
                l = QgsVectorLayer(f"multipolygon?crs={crsDest}&field=id:integer", "xformlayer",  "memory")
                feats = []

                for f in layer.getFeatures():
                    g = f.geometry()
                    g.transform(xform)
                    f.setGeometry(g)
                    feats.append(f)

                l.dataProvider().addFeatures(feats)
                l.updateExtents()
                layer = l

            index = QgsSpatialIndex(layer.getFeatures())

            dindex = self.assignLayer.fields().lookupField(self.distField)
            if dindex == -1:
                self.exception = ValueError('invalid district field for shapefile import')
                return False
            sindex = layer.fields().lookupField(self.importDistField)
            if sindex == -1:
                self.exception = ValueError('invalid source field for shapefile import')
                return False

            total = self.assignLayer.featureCount()
            count = 0
            self.assignLayer.startEditing()
            for f in self.assignLayer.getFeatures():
                g = f.geometry()
                candidates = index.intersects(g.boundingBox())
                for d in layer.getFeatures(candidates):
                    i = g.intersection(d.geometry())
                    if not i.isEmpty() and i.area() > g.area() / 2:
                        self.assignLayer.changeAttributeValue(f.id(), dindex, d[sindex], f[dindex], True)
                        break
                else:
                    self.errors.append(f.id())
                count += 1
                self.setProgress(count/total)
                if self.isCanceled():
                    raise CancelledError()
            self.assignLayer.commitChanges(True)
        except CancelledError:
            self.assignLayer.rollBack(True)
            return False
        except Exception as e:  # pylint: disable=broad-except
            self.assignLayer.rollBack(True)
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
