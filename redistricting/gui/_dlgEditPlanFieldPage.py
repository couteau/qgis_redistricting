# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - New/Edit Plan Wizard - Extra Demographics Page

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
from typing import Optional

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import (
    QModelIndex,
    QObject,
    Qt
)
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
    QWizardPage
)

from ..models import (
    RdsDataField,
    RdsField
)
from ..services import defaults
from ..utils import (
    matchField,
    tr
)
from .RdsFieldTableView import FieldListModel
from .ui.WzpEditPlanFieldPage import Ui_wzpDisplayFields


class PopFieldDelegate(QStyledItemDelegate):
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.popFields: list[RdsField] = []

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        if index.column() == 3:
            editor = QComboBox(parent)
            editor.setFrame(False)
            rect = option.rect
            editor.setGeometry(rect)
            editor.setEditable(False)
            editor.addItems([f.caption for f in self.popFields])
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        if index.column() == 3:
            text = index.model().data(index, Qt.EditRole)
            editor.setCurrentText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QComboBox, model: FieldListModel, index: QModelIndex):
        if index.column() == 3:
            idx = editor.currentIndex()
            model.setData(index, idx, Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() == 1:
            rect = option.rect
            editor.setGeometry(rect)
        else:
            super().updateEditorGeometry(editor, option, index)


class dlgEditPlanFieldPage(Ui_wzpDisplayFields, QWizardPage):
    fields = None

    def __init__(self,  parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.fieldsModel = self.tblDataFields.model()
        self.fieldsModel.fieldType = RdsDataField
        self.tblDataFields.setItemDelegateForColumn(3, PopFieldDelegate(self))

        self.registerField('dataFields', self.tblDataFields, 'fields', self.tblDataFields.fieldsChanged)
        self.tblDataFields.setEnableDragRows(True)

        self.btnAddField.setIcon(
            QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.fexDataField.fieldChanged.connect(self.fieldChanged)
        self.btnAddField.clicked.connect(self.addField)

    def initializePage(self):
        super().initializePage()
        popLayer = self.field("popLayer") or self.field("sourceLayer")
        popField = RdsField(popLayer, self.field("popField"), False, tr("Total Population"))
        popFields: list[RdsField] = [popField, *self.field("popFields")]
        self.fieldsModel.popFields = popFields

        delegate: PopFieldDelegate = self.tblDataFields.itemDelegateForColumn(3)
        delegate.popFields = popFields

        self.tblDataFields.setColumnWidth(0, 120)
        self.tblDataFields.setColumnWidth(1, 120)
        self.tblDataFields.setColumnWidth(2, 32)
        self.tblDataFields.setColumnWidth(3, 120)
        self.tblDataFields.setColumnWidth(6, 32)
        self.fexDataField.setLayer(popLayer)
        if hasattr(self.wizard(), "isComplete"):
            self.setFinalPage(self.wizard().isComplete())
        else:
            self.setFinalPage(True)

    def cleanupPage(self):
        ...

    def fieldChanged(self, field):
        self.btnAddField.setEnabled(field != '' and (
            not self.fexDataField.isExpression() or self.fexDataField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.fexDataField.currentField()
        if not isValid:
            return

        f = self.fieldsModel.appendField(self.fexDataField.layer(), field, isExpression)
        if f and f.isNumeric and not isExpression:
            if matchField(f.field, self.fexDataField.layer(), defaults.VAP_FIELDS):
                for p in self.fieldsModel.popFields:
                    if matchField(p.field, None, defaults.VAP_TOTAL_FIELDS):
                        f.pctbase = p.fieldName

            elif matchField(f.field, self.fexDataField.layer(), defaults.CVAP_FIELDS):
                for p in self.fieldsModel.popFields:
                    if matchField(p.field, None, defaults.CVAP_TOTAL_FIELDS):
                        f.pctbase = p.fieldName

            else:
                f.pctbase = self.field("popField")
