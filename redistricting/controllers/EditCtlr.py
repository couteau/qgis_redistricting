"""QGIS Redistricting Plugin - actions for assignment editing

        begin                : 2024-03-23
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Cryptodira
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
from typing import Optional

from qgis.core import QgsApplication
from qgis.gui import Qgis
from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QObject,
    Qt
)
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialog
)

from ..gui import (
    DlgCopyPlan,
    DlgNewDistrict,
    DockRedistrictingToolbox,
    PaintDistrictsTool,
    PaintMode
)
from ..models import (
    District,
    RedistrictingPlan
)
from ..services import (
    PlanAssignmentEditor,
    PlanCopier
)
from ..utils import tr
from .BaseCtlr import BaseController


class EditAssignmentsController(BaseController):
    def __init__(
        self,
        iface,
        project,
        planManager,
        toolbar,
        assignmentEditor: PlanAssignmentEditor,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.assignmentEditor = assignmentEditor
        self.canvas = self.iface.mapCanvas()
        self.dockwidget: DockRedistrictingToolbox = None
        self.actionToggle: QAction = None

        self.mapTool = PaintDistrictsTool(self.canvas)

        self.actionStartPaintDistricts = QAction(
            QIcon(':/plugins/redistricting/paintpalette.svg'),
            tr('Paint districts'),
            self.iface.mainWindow()
        )
        self.actionStartPaintDistricts.triggered.connect(self.startPaintDistricts)
        self.actionStartPaintDistricts.setEnabled(False)

        self.actionPaintRectangle = QAction(
            QIcon(':/plugins/redistricting/paintrubberband.svg'),
            tr('Paint districts within selection rectangle'),
            self.iface.mainWindow()
        )
        self.actionPaintRectangle.triggered.connect(self.startPaintRectangle)
        self.actionPaintRectangle.setEnabled(False)

        self.actionSelectByGeography = QAction(
            QgsApplication.getThemeIcon('/mActionSelectFreehand.svg'),
            tr('Select by geography units'),
            self.iface.mainWindow()
        )
        self.actionSelectByGeography.triggered.connect(self.selectByGeography)
        self.actionSelectByGeography.setEnabled(False)

        self.actionCommitPlanChanges = QAction(
            QgsApplication.getThemeIcon('/mActionSaveAllEdits.svg'),
            tr('Commit changes'),
            self.iface.mainWindow()
        )
        self.actionCommitPlanChanges.triggered.connect(self.onCommitChanges)
        self.actionCommitPlanChanges.setStatusTip(tr('Save all districting changes to the underlying layer'))
        self.actionCommitPlanChanges.setEnabled(False)

        self.actionSaveAsNew = QAction(
            QgsApplication.getThemeIcon('/mActionFileSaveAs.svg'),
            tr('Save as new'),
            self.iface.mainWindow()
        )
        self.actionSaveAsNew.triggered.connect(self.saveChangesAsNewPlan)
        self.actionSaveAsNew.setStatusTip(tr('Save all unsaved districting changes to a new redistricting plan'))
        self.actionSaveAsNew.setEnabled(False)

        self.actionRollbackPlanChanges = QAction(
            QgsApplication.getThemeIcon('/mActionCancelEdits.svg'),
            tr('Rollback changes'),
            self.iface.mainWindow()
        )
        self.actionRollbackPlanChanges.triggered.connect(self.onRollbackChanges)
        self.actionRollbackPlanChanges.setStatusTip(tr('Discard all unsaved districting changes'))
        self.actionRollbackPlanChanges.setEnabled(False)

    def load(self):
        self.createPlanToolsDockWidget()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)
        self.planManager.planAdded.connect(self.connectPlanSignals)

    def unload(self):
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.planManager.planAdded.disconnect(self.connectPlanSignals)
        self.iface.removeDockWidget(self.dockwidget)
        self.dockwidget.destroy()
        self.dockwidget = None

    def createPlanToolsDockWidget(self):
        """Create the dockwidget with tools for painting districts."""
        dockwidget = DockRedistrictingToolbox(None)

        dockwidget.geoFieldChanged.connect(self.mapTool.setGeoField)
        dockwidget.sourceChanged.connect(self.mapTool.setSourceDistrict)
        dockwidget.targetChanged.connect(self.setDistTarget)
        dockwidget.btnAssign.setDefaultAction(self.actionStartPaintDistricts)
        dockwidget.btnPaintRectangle.setDefaultAction(self.actionPaintRectangle)
        dockwidget.btnSelectByGeography.setDefaultAction(self.actionSelectByGeography)
        dockwidget.btnCommitUpdate.setDefaultAction(self.actionCommitPlanChanges)
        dockwidget.btnSaveAsNew.setDefaultAction(self.actionSaveAsNew)
        dockwidget.btnRollbackUpdate.setDefaultAction(self.actionRollbackPlanChanges)

        self.iface.addDockWidget(Qt.RightDockWidgetArea, dockwidget)

        self.actionToggle = dockwidget.toggleViewAction()
        self.actionToggle.setIcon(QIcon(':/plugins/redistricting/paintdistricts.svg'))
        self.actionToggle.setText(tr('Paint Districts'))
        self.actionToggle.setStatusTip(tr('Show/hide tools for creating/editing districts'))
        self.toolbar.addAction(self.actionToggle)

        self.dockwidget = dockwidget
        return self.dockwidget

    # slots

    def activePlanChanged(self, plan: RedistrictingPlan):
        if not sip.isdeleted(self.canvas):
            self.canvas.unsetMapTool(self.mapTool)

        self.dockwidget.plan = plan
        self.mapTool.plan = plan

        if plan is not None:
            self.actionCommitPlanChanges.setEnabled(plan.assignLayer.isEditable())
            self.actionSaveAsNew.setEnabled(plan.assignLayer.isEditable())
            self.actionRollbackPlanChanges.setEnabled(plan.assignLayer.isEditable())

        self.actionStartPaintDistricts.setEnabled(plan is not None)
        self.actionPaintRectangle.setEnabled(plan is not None)
        self.actionSelectByGeography.setEnabled(plan is not None)

    def connectPlanSignals(self, plan: RedistrictingPlan):
        plan.assignLayer.editingStarted.connect(self.editingStarted)
        plan.assignLayer.editingStopped.connect(self.editingStopped)

    def editingStarted(self):
        if self.sender() == self.planManager.activePlan.assignLayer:
            self.actionCommitPlanChanges.setEnabled(True)
            self.actionSaveAsNew.setEnabled(True)
            self.actionRollbackPlanChanges.setEnabled(True)

    def editingStopped(self):
        if self.sender() == self.planManager.activePlan.assignLayer:
            self.actionCommitPlanChanges.setEnabled(False)
            self.actionSaveAsNew.setEnabled(False)
            self.actionRollbackPlanChanges.setEnabled(False)

    # action slots

    def startPaintDistricts(self):
        if self.planManager.activePlan:
            self.activateMapTool(PaintMode.PaintByGeography)

    def startPaintRectangle(self):
        if self.planManager.activePlan:
            self.activateMapTool(PaintMode.PaintRectangle)

    def selectByGeography(self):
        if self.planManager.activePlan:
            self.activateMapTool(PaintMode.SelectByGeography)

    def saveChangesAsNewPlan(self):
        if not self.checkActivePlan(self.tr('copy')):
            return

        dlgCopyPlan = DlgCopyPlan(self.planManager.activePlan, self.iface.mainWindow())
        dlgCopyPlan.cbxCopyAssignments.hide()

        if dlgCopyPlan.exec_() == QDialog.Accepted:
            copier = PlanCopier(self.planManager.activePlan)
            progress = self.startProgress(self.tr('Creating plan layers...'))
            copier.progressChanged.connect(progress.setValue)
            progress.canceled.connect(copier.cancel)
            plan = copier.copyPlan(dlgCopyPlan.planName, dlgCopyPlan.description,
                                   dlgCopyPlan.geoPackagePath, copyAssignments=True)
            copier.copyBufferedAssignments(plan)
            self.planManager.activePlan.assignLayer.rollBack(True)
            self.planManager.appendPlan(plan)

    def onCommitChanges(self):
        self.planManager.activePlan.assignLayer.commitChanges(True)
        self.planManager.activePlan.assignLayer.triggerRepaint()

    def onRollbackChanges(self):
        self.planManager.activePlan.assignLayer.rollBack(True)
        self.planManager.activePlan.assignLayer.triggerRepaint()

    def createDistrict(self):
        if not self.checkActivePlan('create district'):
            return None

        if self.planManager.activePlan.allocatedDistricts == self.planManager.activePlan.numDistricts:
            self.iface.messageBar().pushMessage(
                self.tr("Warning"), self.tr('All districts have already been allocated'), Qgis.Warning)
            self.dockwidget.setTargetDistrict(None)
            return None

        dlg = DlgNewDistrict(self.planManager.activePlan, self.iface.mainWindow())
        if dlg.exec_() == QDialog.Rejected:
            return None

        dist = District(dlg.districtNumber, name=dlg.districtName, members=dlg.members, description=dlg.description)
        self.planManager.activePlan.districts.append(District)
        self.dockwidget.setTargetDistrict(dist)
        return dist.district

    # helper methods

    def activateMapTool(self, mode):
        if not self.project.layerTreeRoot().findLayer(self.planManager.activePlan.assignLayer).isVisible():
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr(
                    "Cannot paint districts for a plan that is not visible. "
                    "Please toggle the visibility of plan {name}'s assignment layer."
                ).format(name=self.planManager.activePlan.name),
                level=Qgis.Warning,
                duration=5)
            return

        self.mapTool.paintMode = mode
        # if self.mapTool.targetDistrict() is None:
        #    target = self.createDistrict()
        #    self.mapTool.setTargetDistrict(target)
        if self.mapTool.canActivate():
            self.canvas.setMapTool(self.mapTool)
