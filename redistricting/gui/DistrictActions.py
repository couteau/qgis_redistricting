import io
from typing import TYPE_CHECKING
from uuid import UUID

import pandas as pd
from qgis.core import QgsApplication
from qgis.gui import (
    QgsMapMouseEvent,
    QgsMapToolIdentify
)
from qgis.PyQt.QtCore import QMimeData
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QMenu
)

if TYPE_CHECKING:
    from ..redistricting import Redistricting


class DistrictActions:
    def __init__(self, plugin: "Redistricting"):
        self._plugin = plugin
        self.canvas = plugin.canvas
        self.actionCopyDistrict = None
        self.actionPasteDistrict = None
        self.actionZoomToDistrict = None
        self.actionFlashDistrict = None

    def hookCanvasMenu(self):
        self.actionCopyDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/copydistrict.svg'),
            text=self._plugin.tr('Copy district'),
            parent=self._plugin.iface.mainWindow()
        )
        self.actionCopyDistrict.setToolTip(self._plugin.tr('Copy district to clipboard'))
        self.actionCopyDistrict.triggered.connect(self.copyDistrict)

        self.actionPasteDistrict = QAction(
            icon=QgsApplication.getThemeIcon('/mActionDuplicateFeature.svg'),
            text=self._plugin.tr('Paste district'),
            parent=self._plugin.iface.mainWindow()
        )
        self.actionPasteDistrict.setToolTip(self._plugin.tr('Paste district from clipboard'))
        self.actionPasteDistrict.triggered.connect(self.pasteDistrict)

        self.actionZoomToDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/zoomdistrict.svg'),
            text=self._plugin.tr("Zoom to district"),
            parent=self._plugin.iface.mainWindow()
        )
        self.actionZoomToDistrict.triggered.connect(self.zoomToDistrict)

        self.actionFlashDistrict = QAction(
            icon=QIcon(':/plugins/redistricting/flashdistrict.svg'),
            text=self._plugin.tr("Flash district"),
            parent=self._plugin.iface.mainWindow()
        )
        self.actionFlashDistrict.triggered.connect(self.flashDistrict)

        self.canvas.contextMenuAboutToShow.connect(self.addCanvasContextMenuItems)

    def unhookCanvasMenu(self):
        self.canvas.contextMenuAboutToShow.disconnect(self.addCanvasContextMenuItems)

    def canCopyAssignments(self, event: QgsMapMouseEvent):
        i = QgsMapToolIdentify(self.canvas)
        r = i.identify(event.x(), event.y(), layerList=[self._plugin.activePlan.distLayer])
        if r:
            f = r[0].mFeature
            if f[self._plugin.activePlan.distField] != 0:
                self.actionCopyDistrict.setData(f[self._plugin.activePlan.distField])
                return True

        return False

    def canPasteAssignments(self, plan):
        if self._plugin.activePlan is not None:
            cb = QgsApplication.instance().clipboard()
            if cb.mimeData().hasFormat('application/x-redist-planid') and cb.mimeData().hasFormat('application/x-redist-assignments'):
                planid = UUID(bytes=cb.mimeData().data('application/x-redist-planid').data())
                if planid != plan.id:
                    return True

        return False

    def copyDistrict(self):
        cb = QgsApplication.instance().clipboard()
        dist: int = self.actionCopyDistrict.data()
        assignments = self._plugin.activePlan.districts[dist].assignments.to_csv()
        mime = QMimeData()
        mime.setData('application/x-redist-planid', self._plugin.activePlan.id.bytes)
        mime.setData('application/x-redist-assignments', assignments.encode())
        mime.setText(assignments)
        cb.setMimeData(mime)

    def pasteDistrict(self):
        if not self.canPasteAssignments(self._plugin.activePlan):
            return

        cb = QgsApplication.instance().clipboard()
        assignments = pd.read_csv(io.StringIO(cb.mimeData().text()), index_col="fid")

        if not assignments.empty:
            assign = self._plugin.activePlan.startEditing()
            assign.startEditCommand(self._plugin.tr('Paste district'))
            assign.changeAssignments(
                assignments.groupby(self._plugin.activePlan.distField).groups
            )
            assign.endEditCommand()

    def addCanvasContextMenuItems(self, menu: QMenu, event: QgsMapMouseEvent):
        menu.addAction(self.actionCopyDistrict)
        self.actionCopyDistrict.setEnabled(self.canCopyAssignments(event))

        menu.addAction(self.actionPasteDistrict)
        self.actionPasteDistrict.setEnabled(self.canPasteAssignments(self._plugin.activePlan))

    def zoomToDistrict(self):
        if self._plugin.activePlan is None:
            return

        district = self.actionZoomToDistrict.data()
        if not (isinstance(district, int) and 1 <= district <= self._plugin.activePlan.numDistricts):
            return

        fid = self._plugin.activePlan.districts[district]["fid"]
        if fid is not None:
            self._plugin.iface.mapCanvas().zoomToFeatureIds(self._plugin.activePlan.distLayer, [fid])
            self._plugin.iface.mapCanvas().refresh()

    def flashDistrict(self):
        if self._plugin.activePlan is None:
            return

        district = self.actionZoomToDistrict.data()

        if not (isinstance(district, int) and 1 <= district <= self._plugin.activePlan.numDistricts):
            return
        fid = self._plugin.activePlan.districts[district]["fid"]
        if fid is not None:
            self._plugin.iface.mapCanvas().flashFeatureIds(self._plugin.activePlan.distLayer, [fid])
