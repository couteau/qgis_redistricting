# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Redistricting Plugin New Plan Wizard - Districts Page

        begin                : 2022-01-15
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Cryptodira
        email                : stuart@cryptodira.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from typing import List
from qgis.PyQt.QtCore import Qt, QCoreApplication, QAbstractTableModel, QModelIndex, QVariant
from qgis.PyQt.QtWidgets import QWizardPage
from qgis.core import QgsApplication
from .ui.WzpEditPlanFieldPage import Ui_wzpDisplayFields
from ..core import DataField


class DataFieldsModel(QAbstractTableModel):
    _data: List[DataField]
    _headings = [QCoreApplication.translate('Redistricting', 'Field'),
                 QCoreApplication.translate('Redistricting', 'Caption'),
                 QCoreApplication.translate('Redistricting', '∑'),
                 QCoreApplication.translate('Redistricting', '%Pop'),
                 QCoreApplication.translate('Redistricting', '%VAP'),
                 QCoreApplication.translate('Redistricting', '%CVAP'),
                 '']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layer = None
        self._data = []

    @property
    def vapEnabled(self) -> bool:
        return self.parent().field('vapField') is not None

    @property
    def cvapEnabled(self) -> bool:
        return self.parent().field('cvapField') is not None

    @property
    def fields(self) -> List[DataField]:
        return self._data

    @fields.setter
    def fields(self, value: List[DataField]):
        self._data = value

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return 7

    def data(self, index, role):
        if index.row() >= len(self.fields):
            return None

        field = self.fields[index.row()]
        if index.column() == 0:
            if role == Qt.DisplayRole:
                return field.field
            elif role == Qt.DecorationRole:
                return field.icon
        elif index.column() == 1:
            if role == Qt.DisplayRole or role == Qt.EditRole:
                return field.caption
        elif index.column() == 6:
            if role == Qt.DecorationRole:
                return QgsApplication.getThemeIcon("/mActionDeleteSelected.svg")
        elif role == Qt.CheckStateRole:
            if index.column() == 2:
                return Qt.Checked if field.sum else Qt.Unchecked
            elif index.column() == 3:
                return Qt.Checked if field.pctpop else Qt.Unchecked
            elif index.column() == 4:
                return Qt.Checked if field.pctvap and self.vapEnabled else Qt.Unchecked
            elif index.column() == 5:
                return Qt.Checked if field.pctcvap and self.cvapEnabled else Qt.Unchecked
        elif role == Qt.TextAlignmentRole:
            if index.column() in range(2, 6):
                return Qt.AlignCenter

        return QVariant()

    def headerData(self, section, orientation: Qt.Orientation, role):
        if (role == Qt.DisplayRole and orientation == Qt.Horizontal):
            return self._headings[section]

        return None

    def setData(self, index, value, role):
        if not index.isValid() or index.row() >= len(self.fields):
            return False

        field = self.fields[index.row()]
        if not field.isNumeric:
            return False

        if role == Qt.EditRole and index.column() == 1:
            field.caption = value
        elif role == Qt.CheckStateRole:
            if index.column() == 2:
                field.sum = bool(value)
            elif index.column() == 3:
                if value:
                    if field.pctvap:
                        field.pctvap = False
                        i = self.createIndex(index.row(), 4)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                    elif field.pctcvap:
                        field.pctcvap = False
                        i = self.createIndex(index.row(), 5)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                field.pctpop = bool(value)
            elif index.column() == 4 and self.vapEnabled:
                if value:
                    if field.pctpop:
                        field.pctpop = False
                        i = self.createIndex(index.row(), 3)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                    if field.pctcvap:
                        field.pctcvap = False
                        i = self.createIndex(index.row(), 5)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                field.pctvap = bool(value)
            elif index.column() == 5 and self.cvapEnabled:
                if value:
                    if field.pctpop:
                        field.pctpop = False
                        i = self.createIndex(index.row(), 3)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                    if field.pctvap:
                        field.pctvap = False
                        i = self.createIndex(index.row(), 4)
                        self.dataChanged.emit(i, i, [Qt.DisplayRole])
                field.pctcvap = bool(value)
            else:
                return False
        else:
            return False

        return True

    def flags(self, index):
        f = super().flags(index)
        if not index.isValid():
            return f | Qt.ItemIsDropEnabled

        if index.row() < len(self._data):
            f = f | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

        if index.row() >= len(self.fields) or index.column() == 0:
            return f

        field = self.fields[index.row()]
        if index.column() == 1:
            return f | Qt.ItemIsEditable
        elif not field.isNumeric:
            return f

        if index.column() == 2 or index.column() == 3:
            return f | Qt.ItemIsUserCheckable
        elif index.column() == 4 and self.vapEnabled:
            return f | Qt.ItemIsUserCheckable
        elif index.column() == 5 and self.cvapEnabled:
            return f | Qt.ItemIsUserCheckable

        return f

    def appendField(self, field: str, isExpression: bool):
        for f in self._data:
            if f.field == field:
                return

        self.beginInsertRows(QModelIndex(), len(
            self._data), len(self._data))
        self._data.append(DataField(self._layer, field, isExpression))
        self.endInsertRows()

    def deleteField(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self._data.remove(self._data[row])
        self.endRemoveRows()

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def moveField(self, row_source, row_target):
        row_a, row_b = max(row_source, row_target), min(row_source, row_target)
        self.beginMoveRows(QModelIndex(), row_a, row_a, QModelIndex(), row_b)
        self._data.insert(row_target, self._data.pop(row_source))
        self.endMoveRows()

    def __getitem__(self, key: int):
        if key >= 0 and key < len(self._data):
            return self._data[key]


class dlgEditPlanFieldPage(Ui_wzpDisplayFields, QWizardPage):
    fields = None

    def __init__(self,  parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.fieldsModel = DataFieldsModel(self)
        self.tblDataFields.setModel(self.fieldsModel)

        self.registerField('dataFields', self.tblDataFields)

        self.tblDataFields.setColumnWidth(0, 120)
        self.tblDataFields.setColumnWidth(1, 120)
        self.tblDataFields.setColumnWidth(2, 40)
        self.tblDataFields.setColumnWidth(3, 45)
        self.tblDataFields.setColumnWidth(4, 45)
        self.tblDataFields.setColumnWidth(5, 45)
        self.tblDataFields.setColumnWidth(6, 25)
        self.tblDataFields.setEnableDragRows(True)

        self.btnAddField.setIcon(
            QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.fexDataField.fieldChanged.connect(self.fieldChanged)
        self.btnAddField.clicked.connect(self.addField)
        self.tblDataFields.clicked.connect(self.deleteField)

        self.setFinalPage(True)

    def initializePage(self):
        super().initializePage()
        self.fieldsModel._layer = self.field(
            'popLayer') or self.field('sourceLayer')
        self.fexDataField.setLayer(self.field(
            'popLayer') or self.field('sourceLayer'))

    def fieldChanged(self, field):
        self.btnAddField.setEnabled(field != '' and (
            not self.fexDataField.isExpression() or self.fexDataField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.fexDataField.currentField()
        if not isValid:
            return

        self.fieldsModel.appendField(field, isExpression)

    def deleteField(self, index: QModelIndex):
        if index.column() == 6:
            self.fieldsModel.deleteField(index.row())
