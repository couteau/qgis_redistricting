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
from typing import (
    Iterable,
    Optional
)

from qgis.core import (
    QgsApplication,
    QgsFeature,
    QgsVectorLayer
)
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
    DlgNewDistrict,
    DockRedistrictingToolbox,
    PaintDistrictsTool,
    PaintMode
)
from ..models import (
    District,
    RedistrictingPlan
)
from ..services import AssignmentsService
from ..utils import tr
from .BaseCtlr import BaseController


class EditAssignmentsController(BaseController):
    def __init__(
        self,
        iface,
        project,
        planManager,
        toolbar,
        assignmentsService: AssignmentsService,
        parent: Optional[QObject] = None
    ):
        super().__init__(iface, project, planManager, toolbar, parent)
        self.assignmentsService = assignmentsService
        self.canvas = self.iface.mapCanvas()
        self.dockwidget: DockRedistrictingToolbox = None
        self.actionToggle: QAction = None

        self.mapTool = PaintDistrictsTool(self.canvas)
        self.sourceDistrict: District = None
        self.targetDistrict: District = None
        self.geoField: str = None

        self.mapTool.paintingStarted.connect(self.startPaintingFeatures)
        self.mapTool.paintFatures.connect(self.paintFeatures)
        self.mapTool.paintingComplete.connect(self.endPaintingFeatures)
        self.mapTool.paintingCanceled.connect(self.endPaintingFeatures)
        self.mapTool.selectFeatures.connect(self.selectFeatures)

        self.actionStartPaintDistricts = self.actions.createAction(
            'actionStartPaintDistricts',
            QIcon(':/plugins/redistricting/paintpalette.svg'),
            tr('Paint districts'),
            callback=self.startPaintDistricts,
            parent=self.iface.mainWindow()
        )
        self.actionStartPaintDistricts.setEnabled(False)

        self.actionPaintRectangle = self.actions.createAction(
            'actionPaintRectangle',
            QIcon(':/plugins/redistricting/paintrubberband.svg'),
            tr('Paint districts within selection rectangle'),
            callback=self.startPaintRectangle,
            parent=self.iface.mainWindow()
        )
        self.actionPaintRectangle.setEnabled(False)

        self.actionSelectByGeography = self.actions.createAction(
            'actionSelectByGeography',
            QgsApplication.getThemeIcon('/mActionSelectFreehand.svg'),
            tr('Select by geography units'),
            callback=self.selectByGeography,
            parent=self.iface.mainWindow()
        )
        self.actionSelectByGeography.setEnabled(False)

        self.actionCommitPlanChanges = self.actions.createAction(
            'actionCommitPlanChanges',
            QgsApplication.getThemeIcon('/mActionSaveAllEdits.svg'),
            tr('Commit changes'),
            tr('Save all districting changes to the underlying layer'),
            callback=self.onCommitChanges,
            parent=self.iface.mainWindow()
        )
        self.actionCommitPlanChanges.setEnabled(False)

        self.actionSaveAsNew = self.actions.actionSaveAsNew

        self.actionRollbackPlanChanges = self.actions.createAction(
            'actionRollbackPlanChanges',
            QgsApplication.getThemeIcon('/mActionCancelEdits.svg'),
            tr('Rollback changes'),
            tr('Discard all unsaved districting changes'),
            callback=self.onRollbackChanges,
            parent=self.iface.mainWindow()
        )
        self.actionRollbackPlanChanges.setEnabled(False)

        self.actionCreateDistrict = self.actions.createAction(
            'actionCreateDistrict',
            QgsApplication.getThemeIcon('/mActionAdd.svg'),
            tr("Add district"),
            tr('Create a new district and add it to the plan'),
            callback=self.createDistrict,
            parent=self.iface.mainWindow()
        )
        self.actionCreateDistrict.setEnabled(False)

        self.actionEditTargetDistrict = self.actions.createAction(
            'actionEditTargetDistrict',
            QgsApplication.getThemeIcon('/mActionToggleEditing.svg'),
            tr('Edit district'),
            callback=self.editDistrict,
            parent=self.iface.mainWindow()
        )
        self.actionEditTargetDistrict.setEnabled(False)

        self.actionEditSourceDistrict = self.actions.createAction(
            'actionEditSourceDistrict',
            QgsApplication.getThemeIcon('/mActionToggleEditing.svg'),
            tr('Edit district'),
            callback=self.editDistrict,
            parent=self.iface.mainWindow()
        )
        self.actionEditSourceDistrict.setEnabled(False)

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

        dockwidget.geoFieldChanged.connect(self.setGeoField)
        dockwidget.sourceChanged.connect(self.sourceDistrictChanged)
        dockwidget.targetChanged.connect(self.targetDistrictChanged)
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
        self.actionCreateDistrict.setEnabled(
            plan is not None and plan.allocatedDistricts < plan.numDistricts
        )
        self.actionEditTargetDistrict.setEnabled(False)
        self.actionEditSourceDistrict.setEnabled(False)

    def connectPlanSignals(self, plan: RedistrictingPlan):
        if plan.assignLayer:
            plan.assignLayer.editingStarted.connect(self.editingStarted)
            plan.assignLayer.editingStopped.connect(self.editingStopped)
        plan.districtAdded.connect(self.updateCreateDistrictActionEnabled)
        plan.districtRemoved.connect(self.updateCreateDistrictActionEnabled)

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

    def updateCreateDistrictActionEnabled(self, _):
        if self.sender() == self.planManager.activePlan:
            self.actionCreateDistrict.setEnabled(
                self.planManager.activePlan.allocatedDistricts < self.planManager.activePlan.numDistricts
            )

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

    def onCommitChanges(self):
        self.planManager.activePlan.assignLayer.commitChanges(True)
        self.planManager.activePlan.assignLayer.triggerRepaint()

    def onRollbackChanges(self):
        self.planManager.activePlan.assignLayer.rollBack(True)
        self.planManager.activePlan.assignLayer.triggerRepaint()

    def sourceDistrictChanged(self, district: District):
        if district is None:
            self.mapTool.setSourceDistrict(None)
        else:
            self.mapTool.setSourceDistrict(district.district)
        self.actionEditSourceDistrict.setEnabled(district is not None and district.district != 0)
        self.sourceDistrict = district

    def targetDistrictChanged(self, district: District):
        if district is None:
            self.mapTool.setTargetDistrict(None)
        else:
            self.mapTool.setTargetDistrict(district.district)
        self.actionEditTargetDistrict.setEnabled(district is not None and district.district != 0)
        self.targetDistrict = district

    def createDistrict(self):
        if not self.checkActivePlan('create district'):
            return None

        if self.planManager.activePlan.allocatedDistricts == self.planManager.activePlan.numDistricts:
            self.iface.messageBar().pushMessage(
                self.tr("Warning"), self.tr('All districts have already been allocated'), Qgis.Warning)
            return None

        dlg = DlgNewDistrict(self.planManager.activePlan, self.iface.mainWindow())
        if dlg.exec() == QDialog.Rejected:
            return None

        dist = self.planManager.activePlan.addDistrict(
            dlg.districtNumber, dlg.districtName, dlg.members, dlg.description)
        self.project.setDirty()
        self.dockwidget.setTargetDistrict(dist)
        return dist.district

    def editDistrict(self, district: District = None):
        if not district:
            if self.sender() == self.actionEditTargetDistrict:
                district = self.targetDistrict
            elif self.sender() == self.actionEditSourceDistrict:
                district = self.sourceDistrict
            else:
                return

        if district is None or district.district == 0:
            return

        dlg = DlgNewDistrict(self.planManager.activePlan, self.iface.mainWindow())
        dlg.setWindowTitle(tr("Edit District"))
        dlg.sbxDistrictNo.setReadOnly(True)
        dlg.inpName.setText(district.name)
        dlg.sbxMembers.setValue(district.members)
        dlg.txtDescription.setPlainText(district.description)
        if dlg.exec() == QDialog.Accepted:
            district.name = dlg.districtName
            district.members = dlg.members
            district.description = dlg.description
            self.project.setDirty()

    def editSourceDistrict(self):
        self.editDistrict(self.mapTool.sourceDistrict())

    def editTargetDistrict(self):
        self.editDistrict(self.mapTool.targetDistrict())

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
        if self.planManager.activePlan is not None and self.targetDistrict is not None and self.geoField:
            self.canvas.setMapTool(self.mapTool)

    def setGeoField(self, value):
        if value and self.planManager.activePlan is not None and \
                value != self.planManager.activePlan.geoIdField and \
                value not in self.planManager.activePlan.geoFields:
            raise ValueError(tr('Attempt to set invalid geography field on paint tool'))
        self.geoField = value

    def startPaintingFeatures(self, target, source):
        editor = self.assignmentsService.getEditor(self.planManager.activePlan)
        if source is not None:
            msg = tr('Assign features to district %d from %d') % (target, source)
        else:
            msg = tr('Assign features to district %d') % target
        editor.startEditCommand(msg)

    def paintFeatures(self, features: Iterable[QgsFeature], target: int, source: int, endEdit: bool):
        editor = self.assignmentsService.getEditor(self.planManager.activePlan)
        if self.geoField is not None and self.geoField != self.planManager.activePlan.geoIdField:
            values = {str(feature.attribute(self.geoField)) for feature in features}
            features = editor.getDistFeatures(
                self.geoField, values, target, source)

        editor.assignFeaturesToDistrict(features, target, source, self.planManager.activePlan.assignLayer.isEditable())
        if endEdit:
            editor.endEditCommand()

    def endPaintingFeatures(self):
        editor = self.assignmentsService.getEditor(self.planManager.activePlan)
        editor.endEditCommand()

    def cancelPaintingFeaturees(self):
        editor = self.assignmentsService.getEditor(self.planManager.activePlan)
        editor.cancelEditCommand()

    def selectFeatures(
        self,
        features: Iterable[QgsFeature],
        target: int,
        source: int,
        behavior: QgsVectorLayer.SelectBehavior
    ):
        if self.geoField is not None and self.geoField != self.planManager.activePlan.geoIdField:
            editor = self.assignmentsService.getEditor(self.planManager.activePlan)
            values = {str(feature.attribute(self.geoField)) for feature in features}
            features = editor.getDistFeatures(self.geoField, values, target, source)

        self.planManager.activePlan.assignLayer.selectByIds([f.id() for f in features], behavior)
