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
    TYPE_CHECKING,
    Iterable,
    Optional,
    Union
)

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsFieldModel,
    QgsVectorLayer
)
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog

from ..gui import (
    DlgCopyPlan,
    DlgNewDistrict,
    DockRedistrictingToolbox,
    PaintDistrictsTool,
    PaintMode
)
from ..models import (
    DistrictSelectModel,
    GeoFieldsModel,
    RdsDistrict,
    RdsPlan,
    TargetDistrictModel
)
from ..services import (
    AssignmentsService,
    PlanCopier
)
from ..utils import tr
from .base import DockWidgetController

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QAction
else:
    from qgis.PyQt.QtWidgets import QAction


class EditAssignmentsController(DockWidgetController):
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

        self.sourceModel: DistrictSelectModel = None
        self.targetModel: TargetDistrictModel = None
        self.geoFieldsModel: Union[GeoFieldsModel, QgsFieldModel] = None

        self.mapTool = PaintDistrictsTool(self.canvas)
        self.sourceDistrict: Optional[RdsDistrict] = None
        self.targetDistrict: Optional[RdsDistrict] = None
        self.geoField: Optional[str] = None

        self.mapTool.paintingStarted.connect(self.startPaintingFeatures)
        self.mapTool.paintFeatures.connect(self.paintFeatures)
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

        self.actionSaveAsNew = self.actions.createAction(
            'actionSaveAsNew',
            QgsApplication.getThemeIcon('/mActionFileSaveAs.svg'),
            tr('Save as new'),
            tr('Save all unsaved districting changes to a new redistricting plan'),
            callback=self.saveChangesAsNewPlan,
            parent=self.iface.mainWindow()
        )
        self.actionSaveAsNew.setEnabled(False)

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

        self.actionEditDistrict = self.actions.createAction(
            'actionEditDistrict',
            QgsApplication.getThemeIcon('/mActionToggleEditing.svg'),
            tr('Edit district'),
            callback=self.editDistrict,
            parent=self.iface.mainWindow()
        )

        self.actionEditTargetDistrict = self.actions.createAction(
            'actionEditTargetDistrict',
            QgsApplication.getThemeIcon('/mActionToggleEditing.svg'),
            tr('Edit target district'),
            callback=self.editDistrict,
            parent=self.iface.mainWindow()
        )
        self.actionEditTargetDistrict.setEnabled(False)

        self.actionEditSourceDistrict = self.actions.createAction(
            'actionEditSourceDistrict',
            QgsApplication.getThemeIcon('/mActionToggleEditing.svg'),
            tr('Edit source district'),
            callback=self.editDistrict,
            parent=self.iface.mainWindow()
        )
        self.actionEditSourceDistrict.setEnabled(False)

    def load(self):
        super().load()
        self.planManager.activePlanChanged.connect(self.activePlanChanged)
        self.planManager.planAdded.connect(self.connectPlanSignals)
        self.planManager.planRemoved.connect(self.disconnectPlanSignals)

    def unload(self):
        self.planManager.activePlanChanged.disconnect(self.activePlanChanged)
        self.planManager.planAdded.disconnect(self.connectPlanSignals)
        self.planManager.planRemoved.disconnect(self.disconnectPlanSignals)
        super().unload()

    def createDockWidget(self):
        """Create the dockwidget with tools for painting districts and wire up the actions."""
        dockwidget = DockRedistrictingToolbox(None)

        dockwidget.geoFieldChanged.connect(self.setGeoFieldFromIndex)
        dockwidget.sourceChanged.connect(self.sourceDistrictChanged)
        dockwidget.targetChanged.connect(self.targetDistrictChanged)
        dockwidget.btnAssign.setDefaultAction(self.actionStartPaintDistricts)
        dockwidget.btnPaintRectangle.setDefaultAction(self.actionPaintRectangle)
        dockwidget.btnSelectByGeography.setDefaultAction(self.actionSelectByGeography)
        dockwidget.btnCommitUpdate.setDefaultAction(self.actionCommitPlanChanges)
        dockwidget.btnSaveAsNew.setDefaultAction(self.actionSaveAsNew)
        dockwidget.btnRollbackUpdate.setDefaultAction(self.actionRollbackPlanChanges)
        dockwidget.btnAddDistrict.setDefaultAction(self.actionCreateDistrict)
        dockwidget.btnEditTargetDistrict.setDefaultAction(self.actionEditTargetDistrict)
        dockwidget.btnEditSourceDistrict.setDefaultAction(self.actionEditSourceDistrict)

        return dockwidget

    def createToggleAction(self) -> QAction:
        action = super().createToggleAction()
        if action is not None:
            action.setIcon(QIcon(':/plugins/redistricting/paintdistricts.svg'))
            action.setText(tr('Paint Districts'))
            action.setStatusTip(tr('Show/hide tools for creating/editing districts'))

        return action

    # slots

    def activePlanChanged(self, plan: Union[RdsPlan, None]):
        if not sip.isdeleted(self.canvas):
            self.canvas.unsetMapTool(self.mapTool)

        self.dockwidget.plan = plan
        self.mapTool.plan = plan

        if plan is not None:
            self.actionCommitPlanChanges.setEnabled(plan.assignLayer.isEditable())
            self.actionSaveAsNew.setEnabled(plan.assignLayer.isEditable())
            self.actionRollbackPlanChanges.setEnabled(plan.assignLayer.isEditable())
            if len(plan.geoFields) > 0:
                self.geoFieldsModel = GeoFieldsModel(plan)
                i = 0
            else:
                self.geoFieldsModel = QgsFieldModel()
                self.geoFieldsModel.setLayer(plan.assignLayer)
                i = self.geoFieldsModel.indexFromName(plan.geoIdField).row()
            self.dockwidget.cmbGeoSelect.setModel(self.geoFieldsModel)
            self.dockwidget.cmbGeoSelect.setCurrentIndex(i)
            self.setGeoField(plan.geoIdField)

            self.dockwidget.cmbSource.blockSignals(True)
            self.sourceModel = DistrictSelectModel(plan)
            self.dockwidget.cmbSource.setModel(self.sourceModel)
            self.dockwidget.cmbSource.setCurrentIndex(0)
            self.dockwidget.cmbSource.blockSignals(False)

            self.dockwidget.cmbTarget.blockSignals(True)
            self.targetModel = TargetDistrictModel(plan)
            self.dockwidget.cmbTarget.setModel(self.targetModel)
            self.dockwidget.cmbTarget.setCurrentIndex(0)
            self.dockwidget.cmbTarget.blockSignals(False)

            plan.nameChanged.connect(self.dockwidget.planNameChanged)
            plan.assignLayer.undoStack().canUndoChanged.connect(self.dockwidget.btnUndo.setEnabled)
            plan.assignLayer.undoStack().canRedoChanged.connect(self.dockwidget.btnRedo.setEnabled)
            plan.assignLayer.undoStack().undoTextChanged.connect(self.dockwidget.btnUndo.setToolTip)
            plan.assignLayer.undoStack().redoTextChanged.connect(self.dockwidget.btnRedo.setToolTip)
        else:
            self.dockwidget.cmbGeoSelect.setModel(None)
            self.geoFieldsModel = None
            self.dockwidget.cmbSource.setModel(None)
            self.sourceModel = None
            self.dockwidget.cmbTarget.setModel(None)
            self.targetModel = None

        self.actionStartPaintDistricts.setEnabled(plan is not None)
        self.actionPaintRectangle.setEnabled(plan is not None)
        self.actionSelectByGeography.setEnabled(plan is not None)
        self.actionCreateDistrict.setEnabled(
            plan is not None and plan.allocatedDistricts < plan.numDistricts
        )
        self.actionEditTargetDistrict.setEnabled(False)
        self.actionEditSourceDistrict.setEnabled(False)

    def connectPlanSignals(self, plan: RdsPlan):
        if plan.assignLayer:
            plan.assignLayer.editingStarted.connect(self.editingStarted)
            plan.assignLayer.editingStopped.connect(self.editingStopped)
        plan.districtAdded.connect(self.updateCreateDistrictActionEnabled)
        plan.districtRemoved.connect(self.updateCreateDistrictActionEnabled)
        plan.geoFieldsChanged.connect(self.updateGeographies)
        plan.geoIdCaptionChanged.connect(self.updateGeographies)

    def disconnectPlanSignals(self, plan: RdsPlan):
        if plan.assignLayer:
            plan.assignLayer.editingStarted.disconnect(self.editingStarted)
            plan.assignLayer.editingStopped.disconnect(self.editingStopped)
        plan.districtAdded.disconnect(self.updateCreateDistrictActionEnabled)
        plan.districtRemoved.disconnect(self.updateCreateDistrictActionEnabled)
        plan.geoFieldsChanged.disconnect(self.updateGeographies)
        plan.geoIdCaptionChanged.disconnect(self.updateGeographies)

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

    def updateGeographies(self):
        plan: RdsPlan = self.sender()
        if plan is self.activePlan:
            index = self.dockwidget.cmbGeoSelect.currentIndex()
            if plan.geoFields:
                self.geoFieldsModel = GeoFieldsModel(plan)
            else:
                self.geoFieldsModel = QgsFieldModel()
                self.geoFieldsModel.setLayer(plan.assignLayer)

            self.dockwidget.cmbGeoSelect.setModel(self.geoFieldsModel)
            self.dockwidget.cmbGeoSelect.setCurrentIndex(index)
            self.setGeoFieldFromIndex(index)

    # action slots

    def startPaintDistricts(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.PaintByGeography)

    def startPaintRectangle(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.PaintRectangle)

    def selectByGeography(self):
        if self.activePlan:
            self.activateMapTool(PaintMode.SelectByGeography)

    def onCommitChanges(self):
        self.activePlan.assignLayer.commitChanges(True)
        self.activePlan.assignLayer.triggerRepaint()

    def onRollbackChanges(self):
        self.activePlan.assignLayer.rollBack(True)
        self.activePlan.assignLayer.triggerRepaint()

    def sourceDistrictChanged(self, index: int):
        if index is None or index == -1:
            district = None
        elif self.sourceModel is not None:
            district = self.sourceModel.districtFromIndex(index)
        else:
            district = None

        if district is None:
            self.mapTool.setSourceDistrict(None)
        else:
            self.mapTool.setSourceDistrict(district.district)
        self.actionEditSourceDistrict.setEnabled(district is not None and district.district != 0)
        self.sourceDistrict = district

    def targetDistrictChanged(self, index: Union[int, None]):
        if index is None or index == -1:
            district = None
        elif self.targetModel is not None:
            district = self.targetModel.districtFromIndex(index)
        else:
            district = None

        if district is None:
            self.mapTool.setTargetDistrict(None)
        else:
            self.mapTool.setTargetDistrict(district.district)
        self.actionEditTargetDistrict.setEnabled(district is not None and district.district != 0)
        self.targetDistrict = district

    def createDistrict(self):
        if not self.checkActivePlan('create district'):
            return None

        if self.activePlan.allocatedDistricts == self.activePlan.numDistricts:
            self.iface.messageBar().pushMessage(
                self.tr("Warning"), self.tr('All districts have already been allocated'), Qgis.MessageLevel.Warning)
            return None

        dlg = DlgNewDistrict(self.activePlan, self.iface.mainWindow())
        if dlg.exec() == QDialog.DialogCode.Rejected:
            return None

        dist = self.activePlan.addDistrict(
            dlg.districtNumber, dlg.districtName, dlg.members, dlg.description
        )
        self.project.setDirty()
        i = self.targetModel.indexFromDistrict(dist)
        self.dockwidget.cmbTarget.setCurrentIndex(i)
        return dist.district

    def editDistrict(self, district: Optional[RdsDistrict] = None):
        if not isinstance(district, RdsDistrict):
            if self.sender() == self.actionEditTargetDistrict:
                district = self.targetDistrict
            elif self.sender() == self.actionEditSourceDistrict:
                district = self.sourceDistrict
            elif self.sender() == self.actionEditDistrict and self.actionEditDistrict.data() is not None:
                district = self.actionEditDistrict.data()
            else:
                return

        if district is None or district.district == 0:
            return

        dlg = DlgNewDistrict(self.activePlan, self.iface.mainWindow())
        dlg.setWindowTitle(tr("Edit District"))
        dlg.sbxDistrictNo.setValue(district.district)
        dlg.sbxDistrictNo.setReadOnly(True)
        dlg.inpName.setText(district.name)
        dlg.sbxMembers.setValue(district.members)
        dlg.txtDescription.setPlainText(district.description)
        dlg.buttonBox.button(dlg.buttonBox.Ok).setEnabled(True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            district.name = dlg.districtName
            district.members = dlg.members
            district.description = dlg.description
            self.project.setDirty()

    def editSourceDistrict(self):
        self.editDistrict(self.sourceDistrict)

    def editTargetDistrict(self):
        self.editDistrict(self.targetDistrict)

    def saveChangesAsNewPlan(self):
        if not self.checkActivePlan(self.tr('save changes to new plan')):
            return

        if not self.activePlan.assignLayer.isEditable():
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr("Cannot save changes to no plan: active plan has no unsaved changes."),
                Qgis.MessageLevel.Warning
            )
            return

        dlgCopyPlan = DlgCopyPlan(self.activePlan, self.iface.mainWindow())
        dlgCopyPlan.cbxCopyAssignments.hide()

        if dlgCopyPlan.exec() == QDialog.DialogCode.Accepted:
            copier = PlanCopier(self.planManager.activePlan)
            plan = copier.copyPlan(dlgCopyPlan.planName, dlgCopyPlan.description,
                                   dlgCopyPlan.geoPackagePath, copyAssignments=True)

            self.planManager.appendPlan(plan, False)
            copier.copyBufferedAssignments(plan)
            self.planManager.activePlan.assignLayer.rollBack(True)
            self.planManager.setActivePlan(plan)
            self.project.setDirty()

    # helper methods

    def activateMapTool(self, mode):
        if not self.project.layerTreeRoot().findLayer(self.planManager.activePlan.assignLayer).isVisible():
            self.iface.messageBar().pushMessage(
                self.tr("Oops!"),
                self.tr(
                    "Cannot paint districts for a plan that is not visible. "
                    "Please toggle the visibility of plan {name}'s assignment layer."
                ).format(name=self.planManager.activePlan.name),
                level=Qgis.MessageLevel.Warning,
                duration=5)
            return

        self.mapTool.paintMode = mode
        if self.activePlan is not None and self.targetDistrict is not None and self.geoField:
            self.canvas.setMapTool(self.mapTool)

    def setGeoFieldFromIndex(self, index: int):
        if index == -1:
            self.setGeoField(self.activePlan.geoIdField if self.activePlan else None)
            return

        if isinstance(self.geoFieldsModel, QgsFieldModel):
            field = self.geoFieldsModel.fields().field(index).name()
        else:
            field = self.geoFieldsModel.fields[index].fieldName
        self.setGeoField(field)

    def setGeoField(self, value):
        if self.activePlan is None:
            return

        if value is not None and value != self.activePlan.geoIdField and (
            (len(self.activePlan.geoFields) != 0 and value not in self.activePlan.geoFields) or
            (len(self.activePlan.geoFields) == 0 and value not in self.activePlan.geoLayer.fields().names())
        ):
            raise ValueError(tr('Attempt to set invalid geography field on paint tool'))

        self.geoField = value

    def startPaintingFeatures(self, target, source):
        editor = self.assignmentsService.getEditor(self.activePlan)
        if source is not None:
            msg = tr('Assign features to district %d from %d') % (target, source)
        else:
            msg = tr('Assign features to district %d') % target
        editor.startEditCommand(msg)

    def paintFeatures(self, features: Iterable[QgsFeature], target: int, source: Union[int, None], endEdit: bool):
        editor = self.assignmentsService.getEditor(self.planManager.activePlan)
        if self.geoField is not None and self.geoField != self.planManager.activePlan.geoIdField:
            values = {feature.attribute(self.geoField) for feature in features}
            features = editor.getDistFeatures(
                self.geoField, values, target, source)

        editor.assignFeaturesToDistrict(features, target)
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
