# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - QDockWidget with tools for painting districts

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
from typing import List, Optional, Any
from qgis.PyQt.QtGui import QPixmap, QIcon, QColor
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import Qt, QObject, QVariant, pyqtSignal, QAbstractListModel, QModelIndex
from qgis.core import QgsApplication, QgsFieldModel
from .ui.DistrictTools import Ui_qdwDistrictTools
from ..core import BaseDistrict, RedistrictingPlan, GeoFieldsModel, tr, showHelp


class DistrictSelectModel(QAbstractListModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = ...):
        super().__init__(parent)
        self._offset = 2
        self._plan = plan

    def updateDistricts(self, newValue: List[BaseDistrict], oldValue: List[BaseDistrict]):
        added = set(newValue) - set(oldValue)
        removed = set(oldValue) - set(newValue)

        for dist in removed:
            i = oldValue.index(dist)
            self.beginRemoveRows(QModelIndex(), i+self._offset, i+self._offset)
            self.endInsertRows()

        for dist in added:
            i = newValue.index(dist)
            self.beginInsertRows(QModelIndex(), i+self._offset, i+self._offset)
            self.endInsertRows()

    def districtNameChanged(self, newValue, oldValue):  # pylint: disable=unused-argument
        self.dataChanged.emit(
            self.createIndex(self._offset + 1, 0),
            self.createIndex(self._plan.allocatedDistricts + self._offset, 0),
            {Qt.DisplayRole}
        )

    def indexFromDistrict(self, district):
        if district in self._plan.districts:
            i = self._plan.districts.index(district)
            return 1 if i == 0 else i + self._offset

        return 0

    def rowCount(self, parent: QModelIndex):  # pylint: disable=unused-argument
        return self._offset if self._plan.allocatedDistricts == 0 else self._plan.allocatedDistricts + self._offset + 1

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role in {Qt.DisplayRole, Qt.EditRole}:
            if row == 0:
                return tr('All')
            if row == 1:
                return tr('Unassigned')
            if row > self._offset:
                return self._plan.districts[row-self._offset].name

        if role == Qt.DecorationRole:
            if row == 0:
                return QgsApplication.getThemeIcon('/mActionSelectAll.svg')

            if row == 1:
                pixmap = QPixmap(64, 64)
                pixmap.fill(QColor(160, 160, 160))
                return QIcon(pixmap)

            if row > self._offset:
                pixmap = QPixmap(64, 64)
                pixmap.fill(self._plan.districts[row-self._offset].color)
                return QIcon(pixmap)

        if role == Qt.AccessibleDescriptionRole and row == self._offset:
            return 'separator'

        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.row() == self._offset:
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class SourceDistrictModel(DistrictSelectModel):
    def __init__(self, plan: RedistrictingPlan, parent: Optional[QObject] = None):
        super().__init__(plan, parent)
        self._offset = 3

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if row == 2:
            if role == Qt.DisplayRole or role == Qt.EditRole:
                return tr('Selected')
            if role == Qt.DecorationRole:
                return QgsApplication.getThemeIcon('/mActionProcessSelected.svg')

        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if index.row() == 2 and \
                self._plan.assignLayer.selectedFeatureCount() == 0 and \
                self._plan.popLayer.selectedFeatureCount() == 0 and \
                self._plan.sourceLayer.selectedFeatureCount() == 0:
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class TargetDistrictModel(DistrictSelectModel):
    def data(self, index: QModelIndex, role: int = ...) -> Any:
        row = index.row()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if row == 0:
                return tr('New district')

        elif role == Qt.DecorationRole:
            if row == 0:
                return QgsApplication.getThemeIcon('/mActionAdd.svg')

        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index)
        if (index.row() == 0 and self._plan.allocatedDistricts == self._plan.numDistricts):
            flags = flags & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
        return flags


class DockRedistrictingToolbox(Ui_qdwDistrictTools, QDockWidget):

    _plan: RedistrictingPlan = None
    geoFieldChanged = pyqtSignal(str)
    sourceChanged = pyqtSignal(object)
    targetChanged = pyqtSignal(object)

    @property
    def plan(self) -> RedistrictingPlan:
        return self._plan

    @plan.setter
    def plan(self, value: RedistrictingPlan):
        if self._plan:
            self._plan.planChanged.disconnect(self.reloadFields)
            self._plan.assignLayer.undoStack().undoTextChanged.disconnect(self.btnUndo.setToolTip)
            self._plan.assignLayer.undoStack().redoTextChanged.disconnect(self.btnRedo.setToolTip)
            self._plan.assignLayer.undoStack().canUndoChanged.disconnect(self.btnUndo.setEnabled)
            self._plan.assignLayer.undoStack().canRedoChanged.disconnect(self.btnRedo.setEnabled)

        self._plan = value

        if self._plan:
            self.lblPlanName.setText(self._plan.name)
            if len(self._plan.geoFields) > 0:
                model = GeoFieldsModel(self._plan, self)
                i = 0
            else:
                model = QgsFieldModel(self)
                model.setLayer(self._plan.assignLayer)
                i = model.indexFromName(self._plan.geoIdField).row()

            self.cmbGeoSelect.setModel(model)
            self.cmbGeoSelect.setCurrentIndex(i)

            self.cmbSource.blockSignals(True)
            self.cmbSource.setModel(DistrictSelectModel(self._plan, self))
            self.cmbSource.setCurrentIndex(0)
            self.cmbSource.blockSignals(False)

            self.cmbTarget.blockSignals(True)
            self.cmbTarget.setModel(TargetDistrictModel(self._plan, self))
            self.cmbTarget.setCurrentIndex(0)
            self.cmbTarget.blockSignals(False)

            self._plan.planChanged.connect(self.reloadFields)
            self._plan.assignLayer.undoStack().canUndoChanged.connect(self.btnUndo.setEnabled)
            self._plan.assignLayer.undoStack().canRedoChanged.connect(self.btnRedo.setEnabled)
            self._plan.assignLayer.undoStack().undoTextChanged.connect(self.btnUndo.setToolTip)
            self._plan.assignLayer.undoStack().redoTextChanged.connect(self.btnRedo.setToolTip)
        else:
            self.lblPlanName.setText(tr('No plan selected'))
            self.cmbGeoSelect.clear()
            self.cmbSource.clear()
            self.cmbTarget.clear()

        self.cmbSource.setEnabled(self._plan is not None)
        self.cmbTarget.setEnabled(self._plan is not None)
        self.cmbGeoSelect.setEnabled(self._plan is not None)

    def __init__(self, plan, parent=None):
        super(DockRedistrictingToolbox, self).__init__(parent)
        self.setupUi(self)

        self.cmbGeoSelect.currentIndexChanged.connect(self.cmbGeoFieldChanged)
        self.cmbTarget.currentIndexChanged.connect(self.cmbTargetChanged)
        self.cmbSource.currentIndexChanged.connect(self.cmbSourceChanged)

        self.btnUndo.setIcon(QgsApplication.getThemeIcon('/mActionUndo.svg'))
        self.btnRedo.setIcon(QgsApplication.getThemeIcon('/mActionRedo.svg'))
        self.btnUndo.setEnabled(False)
        self.btnRedo.setEnabled(False)
        self.btnUndo.clicked.connect(self.undo)
        self.btnRedo.clicked.connect(self.redo)

        self.btnHelp.setIcon(QgsApplication.getThemeIcon('/mActionHelpContents.svg'))
        self.btnHelp.clicked.connect(self.btnHelpClicked)

        self.plan = plan

    def undo(self):
        if self._plan and self._plan.assignLayer:
            self._plan.assignLayer.undoStack().undo()
            self._plan.assignLayer.triggerRepaint()

    def redo(self):
        if self._plan and self._plan.assignLayer:
            self._plan.assignLayer.undoStack().redo()
            self._plan.assignLayer.triggerRepaint()

    def setTargetDistrict(self, district):
        i = self.cmbTarget.model().indexFromDistrict(district)
        self.cmbTarget.setCurrentIndex(i)

    def reloadFields(self, plan, prop, newValue, oldValue):
        if plan != self._plan:
            return

        if prop == 'districts':
            self.cmbSource.model().updateDistricts(newValue, oldValue)
            self.cmbTarget.model().updateDistricts(newValue, oldValue)
        elif prop == 'geo-fields':
            index = self.cmbGeoSelect.currentIndex()
            if self._plan.geoFields:
                model = GeoFieldsModel(self._plan, self)
            else:
                model = QgsFieldModel(self)
                model.setLayer(self._plan.assignLayer)

            self.cmbGeoSelect.setModel(model)
            self.cmbGeoSelect.setCurrentIndex(index)
            if isinstance(model, QgsFieldModel):
                field = model.fields().field(index).name()
            else:
                field = model.fields[index].fieldName
            self.geoFieldChanged.emit(field)
        elif prop == 'name':
            self.lblPlanName.setText(self._plan.name)

    def cmbGeoFieldChanged(self, index):
        if index == -1:
            self.geoFieldChanged.emit(
                self._plan.geoIdField if self._plan else None)
            return

        model = self.cmbGeoSelect.model()
        if isinstance(model, QgsFieldModel):
            field = model.fields().field(index).name()
        else:
            field = model.fields[index].fieldName
        self.geoFieldChanged.emit(field)

    def cmbTargetChanged(self, index):
        if index < 2:
            self.targetChanged.emit(0 if index == 1 else None)
        elif index >= 3:
            dist = self._plan.districts[index-2]
            self.targetChanged.emit(dist.district)

    def cmbSourceChanged(self, index):
        if index < 2:
            self.sourceChanged.emit(0 if index == 1 else None)
        elif index >= 3:
            dist = self._plan.districts[index-2]
            self.sourceChanged.emit(dist.district)

    def btnHelpClicked(self):
        showHelp('usage/toolbox.html')
