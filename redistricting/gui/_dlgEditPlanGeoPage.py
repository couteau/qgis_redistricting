# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Redistricting Plugin New Plan Wizard - Geography Page

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
from qgis.PyQt.QtCore import Qt, QCoreApplication, QVariant, QAbstractTableModel, QModelIndex
from qgis.PyQt.QtWidgets import QWidget, QWizardPage, QHeaderView, QComboBox, QStyledItemDelegate, QStyleOptionViewItem
from qgis.core import QgsApplication, QgsVectorLayer, QgsMapLayerProxyModel
from .ui.WzpEditPlanGeoPage import Ui_wzpAddlGeography
from ..core import Field


class GeoFieldsModel(QAbstractTableModel):

    _headings = [QCoreApplication.translate(
        'Redistricting', 'Field'), QCoreApplication.translate('Redistricting', 'Caption')]

    def __init__(self, parent=None, layer=None):
        super().__init__(parent)
        self._layer = layer
        self._data: List[Field] = []

    @property
    def fields(self) -> List[Field]:
        return self._data

    @fields.setter
    def fields(self, value):
        if len(value) == 0 and len(self._data) == 0:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._data))
        self._data = []
        self.endRemoveRows()
        if value is not None:
            self.beginInsertRows(QModelIndex(), 0, len(value))
            self._data = value
            self.endInsertRows()

    def rowCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return len(self._data)

    def columnCount(self, parent: QModelIndex = ...) -> int:  # pylint: disable=unused-argument
        return 3

    def data(self, index: QModelIndex, role):
        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col == 0:
                return self._data[row].field
            if col == 1:
                return self._data[row].caption
        elif role == Qt.DecorationRole:
            if self._layer and col == 0:
                return self._data[row].icon
            if col == 2:
                return QgsApplication.getThemeIcon("/mActionDeleteSelected.svg")

        return QVariant()

    def headerData(self, section, orientation: Qt.Orientation, role):
        if role == Qt.DisplayRole and section < 2:
            if orientation == Qt.Horizontal:
                return self._headings[section]
            else:
                return str(section+1)

        return None

    def setData(self, index, value, role):
        if not index.isValid() or index.row() >= len(self._data):
            return False

        if role == Qt.EditRole and index.column() == 1:
            self._data[index.row()].caption = value
            return True

        return False

    def appendField(self, field, isExpression=False, caption=None):
        for f in self._data:
            if f.field == field:
                return

        self.beginInsertRows(QModelIndex(),
                             len(self._data),
                             len(self._data))
        self._data.append(Field(self._layer, field, isExpression, caption))
        self.endInsertRows()

    def deleteField(self, row):
        self.beginRemoveRows(QModelIndex(), row, row)
        self._data.remove(self._data[row])
        self.endRemoveRows()

    def flags(self, index):
        f = super().flags(index)
        if not index.isValid():
            return f | Qt.ItemIsDropEnabled

        if index.row() < len(self._data):
            f = f | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled

        if index.column() == 1:
            f = f | Qt.ItemIsEditable

        return f

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def moveField(self, row_source, row_target):
        row_a, row_b = max(row_source, row_target), min(row_source, row_target)
        self.beginMoveRows(QModelIndex(), row_a, row_a, QModelIndex(), row_b)
        self._data.insert(row_target, self._data.pop(row_source))
        self.endMoveRows()


class GeoFieldDelegate(QStyledItemDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        if index.column() == 1:
            editor = QComboBox(parent)
            editor.setFrame(False)
            rect = option.rect
            # rect.setTopLeft(editor.parent().mapToGlobal(rect.topLeft()))
            editor.setGeometry(rect)
            editor.setEditable(True)
            editor.addItems([
                QCoreApplication.translate('Redistricting', 'Block'),
                QCoreApplication.translate('Redistricting', 'Block Group'),
                QCoreApplication.translate('Redistricting', 'Tract'),
                QCoreApplication.translate('Redistricting', 'Precinct/VTD'),
                QCoreApplication.translate('Redistricting', 'County/Parish'),
            ])
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        if index.column() == 1:
            text = index.model().data(index, Qt.EditRole)
            editor.setCurrentText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QComboBox, model: GeoFieldsModel, index: QModelIndex):
        if index.column() == 1:
            text = editor.currentText()
            model.setData(index, text, Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() == 1:
            rect = option.rect
            # rect.setTopLeft(editor.parent().mapToGlobal(rect.topLeft()))
            editor.setGeometry(rect)
        else:
            super().updateEditorGeometry(editor, option, index)


class dlgEditPlanGeoPage(Ui_wzpAddlGeography, QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.fieldsModel = GeoFieldsModel(self)
        self.tblAddlGeography.setModel(self.fieldsModel)

        self.registerField('sourceLayer*', self.cmbSourceLayer)
        self.registerField('geoIdField*', self.cmbGeoIDField)
        self.registerField('geoCaption', self.cmbGeoCaption, 'currentText', self.cmbGeoCaption.currentTextChanged)
        self.registerField('geoFields', self.tblAddlGeography)

        # Annoyingly, loading the UI sets the layer property of a QgsLayerCombo to
        # the first layer in the project, even if allowEmptyLayer is set to true.
        # Clear it to put it into a sane default state.
        self.cmbSourceLayer.setLayer(None)
        self.cmbSourceLayer.layerChanged.connect(self.setSourceLayer)

        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(2,
                                                                      QHeaderView.ResizeToContents)
        self.tblAddlGeography.setColumnWidth(2, 30)
        self.tblAddlGeography.setItemDelegateForColumn(
            1, GeoFieldDelegate(self))

        self.btnAddAddlGeoField.setIcon(
            QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.cmbAddlGeoField.fieldChanged.connect(self.fieldChanged)
        self.btnAddAddlGeoField.clicked.connect(self.addField)
        self.tblAddlGeography.clicked.connect(self.deleteField)
        self.tblAddlGeography.setEnableDragRows(True)

    def initializePage(self):
        super().initializePage()
        self.cmbSourceLayer.setFilters(
            QgsMapLayerProxyModel.Filter.VectorLayer)

        sourceLayer = self.field('sourceLayer')
        if isinstance(sourceLayer, QVariant) and sourceLayer.isNull():
            sourceLayer = None
        self.cmbSourceLayer.setLayer(sourceLayer)
        self.cmbGeoIDField.setLayer(sourceLayer)
        self.cmbAddlGeoField.setLayer(sourceLayer)
        self.setSourceLayer(sourceLayer)

    def setSourceLayer(self, layer: QgsVectorLayer):
        if layer and not self.field('geoIdField'):
            if layer.fields().lookupField('geoid20') != -1:
                self.cmbGeoIDField.setField('geoid20')
            elif layer.fields().lookupField('geoid30') != -1:
                self.cmbGeoIDField.setField('geoid30')
            elif layer.fields().lookupField('geoid10') != -1:
                self.cmbGeoIDField.setField('geoid10')
            elif layer.fields().lookupField('geoid') != -1:
                self.cmbGeoIDField.setField('geoid')
            elif layer.fields().lookupField('block') != -1:
                self.cmbGeoIDField.setField('block')

        if self.fieldsModel._layer != layer:
            self.cmbAddlGeoField.setField(None)
            self.fieldsModel._layer = layer
            self.fieldsModel.fields = []

    def fieldChanged(self, field):
        self.btnAddAddlGeoField.setEnabled(field != '' and (
            not self.cmbAddlGeoField.isExpression() or self.cmbAddlGeoField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.cmbAddlGeoField.currentField()
        if not isValid:
            return

        self.fieldsModel.appendField(field, isExpression)

    def deleteField(self, index: QModelIndex):
        if index.column() == 2:
            self.fieldsModel.deleteField(index.row())
