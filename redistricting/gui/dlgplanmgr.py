# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - Plan Manager Dialog

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
from typing import (
    TYPE_CHECKING,
    Optional
)

from qgis.PyQt.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QSize,
    Qt,
    pyqtSignal
)
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHeaderView,
    QWidget
)

from .ui.DlgSelectPlan import Ui_dlgSelectPlan

if TYPE_CHECKING:
    from qgis.PyQt.QtCore import QT_VERSION
    if QT_VERSION >= 0x060000:
        from PyQt6.QtGui import QAction  # type: ignore[import]
    else:
        from PyQt5.QtWidgets import QAction  # type: ignore[import]

else:
    from qgis.PyQt.QtGui import QAction


class DlgSelectPlan(Ui_dlgSelectPlan, QDialog):
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None,
                 flags: Qt.WindowType = Qt.WindowType.Dialog):
        super().__init__(parent, flags)
        self.setupUi(self)
        self._newAction: QAction = None
        self._selectAction: QAction = None
        self._editAction: QAction = None
        self._deleteAction: QAction = None
        self.btnClose.clicked.connect(self.close)

    def model(self):
        return self.lvwPlans.model(0)

    def setModel(self, model: QAbstractItemModel):
        if self.lvwPlans.model() is not None:
            self.lvwPlans.selectionModel().currentRowChanged.disconnect(self.viewCurrentRowChanged)

        self.lvwPlans.setModel(model)
        if model is None:
            return

        for i in range(model.columnCount()):
            sizeHint = model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.SizeHintRole)
            if isinstance(sizeHint, QSize):
                self.lvwPlans.setColumnWidth(i, sizeHint.width())
        # self.lvwPlans.resizeColumnsToContents()
        # self.lvwPlans.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lvwPlans.horizontalHeader().setSectionResizeMode(model.columnCount() - 1, QHeaderView.Stretch)
        self.lvwPlans.selectionModel().currentRowChanged.connect(self.viewCurrentRowChanged)

    def currentIndex(self):
        return self.lvwPlans.currentIndex().row()

    def setCurrentIndex(self, index: int):
        self.lvwPlans.setCurrentIndex(self.lvwPlans.model().createIndex(index, 0))

    def viewCurrentRowChanged(self, index: QModelIndex, oldIndex: QModelIndex):  # pylint: disable=unused-argument
        self.currentIndexChanged.emit(index.row())

    def setNewAction(self, action: QAction):
        if self._newAction is not None:
            self.btnNew.clicked.disconnect(self._newAction.trigger)
            self._newAction.changed.disconnect(self.newChanged)

        self._newAction = action

        if self._newAction is not None:
            self.btnNew.setToolTip(self._newAction.toolTip())
            self.btnNew.clicked.connect(self._newAction.trigger)
            self._newAction.changed.connect(self.newChanged)

    def setSelectAction(self, action: QAction):
        if self._selectAction is not None:
            self.btnSelect.clicked.disconnect(self._selectAction.trigger)
            self._selectAction.changed.disconnect(self.selectChanged)

        self._selectAction = action

        if self._selectAction is not None:
            self.btnSelect.setToolTip(self._selectAction.toolTip())
            self.btnSelect.clicked.connect(self._selectAction.trigger)
            self._selectAction.changed.connect(self.selectChanged)

    def setEditAction(self, action: QAction):
        if self._editAction is not None:
            self.btnEdit.clicked.disconnect(self._editAction.trigger)
            self._editAction.changed.disconnect(self.editChanged)

        self._editAction = action

        if self._editAction is not None:
            self.btnEdit.setToolTip(self._editAction.toolTip())
            self.btnEdit.clicked.connect(self._editAction.trigger)
            self._editAction.changed.connect(self.editChanged)

    def setDeleteAction(self, action: QAction):
        if self._deleteAction is not None:
            self.btnDelete.clicked.disconnect(self._deleteAction.trigger)
            self._deleteAction.changed.disconnect(self.deleteChanged)

        self._deleteAction = action

        if self._deleteAction is not None:
            self.btnDelete.setToolTip(self._deleteAction.toolTip())
            self.btnDelete.clicked.connect(self._deleteAction.trigger)
            self._deleteAction.changed.connect(self.deleteChanged)

    def newChanged(self):
        self.btnNew.setEnabled(self._newAction.isEnabled())

    def selectChanged(self):
        self.btnSelect.setEnabled(self._selectAction.isEnabled())

    def editChanged(self):
        self.btnEdit.setEnabled(self._editAction.isEnabled())

    def deleteChanged(self):
        self.btnDelete.setEnabled(self._deleteAction.isEnabled())
