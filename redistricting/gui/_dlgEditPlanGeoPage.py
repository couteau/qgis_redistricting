# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - New/Edit Plan Wizard - Geography Page

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
from qgis.core import (
    QgsApplication,
    QgsMapLayerProxyModel,
    QgsVectorLayer
)
from qgis.PyQt.QtCore import (
    QModelIndex,
    Qt,
    QVariant
)
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
    QWizardPage
)

from ..core import defaults
from ..core.utils import getDefaultField
from .RdsFieldTableView import FieldListModel
from .ui.WzpEditPlanGeoPage import Ui_wzpAddlGeography


class GeoFieldDelegate(QStyledItemDelegate):
    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:
        if index.column() == 1:
            editor = QComboBox(parent)
            editor.setFrame(False)
            rect = option.rect
            editor.setGeometry(rect)
            editor.setEditable(True)
            editor.addItems(defaults.GEOID_LABELS)
            return editor
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor: QComboBox, index: QModelIndex):
        if index.column() == 1:
            text = index.model().data(index, Qt.EditRole)
            editor.setCurrentText(text)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor: QComboBox, model: FieldListModel, index: QModelIndex):
        if index.column() == 1:
            text = editor.currentText()
            model.setData(index, text, Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() == 1:
            rect = option.rect
            editor.setGeometry(rect)
        else:
            super().updateEditorGeometry(editor, option, index)


class dlgEditPlanGeoPage(Ui_wzpAddlGeography, QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.fieldsModel = self.tblAddlGeography.model()

        self.registerField('sourceLayer*', self.cmbSourceLayer)
        self.registerField('geoIdField*', self.cmbGeoIDField)
        self.registerField('geoCaption', self.cmbGeoCaption, 'currentText', self.cmbGeoCaption.currentTextChanged)
        self.registerField('geoFields', self.tblAddlGeography, 'fields', self.tblAddlGeography.fieldsChanged)

        # Annoyingly, loading the UI sets the layer property of a QgsLayerCombo to
        # the first layer in the project, even if allowEmptyLayer is set to true.
        # Clear it to put it into a sane default state.
        self.cmbSourceLayer.setLayer(None)
        self.cmbSourceLayer.layerChanged.connect(self.setGeoLayer)

        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tblAddlGeography.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tblAddlGeography.setItemDelegateForColumn(1, GeoFieldDelegate(self))

        self.cmbGeoCaption.addItems(defaults.GEOID_LABELS)

        self.btnAddAddlGeoField.setIcon(QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.cmbAddlGeoField.fieldChanged.connect(self.fieldChanged)
        self.btnAddAddlGeoField.clicked.connect(self.addField)
        self.tblAddlGeography.setEnableDragRows(True)

    def initializePage(self):
        super().initializePage()
        self.cmbSourceLayer.setFilters(
            QgsMapLayerProxyModel.Filter.VectorLayer)

        geoLayer = self.field('sourceLayer')
        if isinstance(geoLayer, QVariant) and geoLayer.isNull():
            geoLayer = None
        self.cmbSourceLayer.setLayer(geoLayer)
        self.cmbGeoIDField.setLayer(geoLayer)
        self.cmbAddlGeoField.setLayer(geoLayer)
        self.setGeoLayer(geoLayer)
        self.setFinalPage(self.wizard().isComplete())

    def cleanupPage(self):
        ...  # prevent fields from being reset

    def setGeoLayer(self, layer: QgsVectorLayer):
        if self.cmbGeoIDField.layer() != layer:
            field = self.field('geoIdField')
            self.cmbGeoIDField.setLayer(layer)
            if layer:
                if field and layer.fields().lookupField(field) != -1:
                    self.cmbGeoIDField.setField(field)
                else:
                    self.cmbGeoIDField.setField(getDefaultField(layer, defaults.GEOID_FIELDS))

        if self.cmbAddlGeoField.layer() != layer:
            self.cmbAddlGeoField.setField(None)
            self.fieldsModel.fields = []
            self.cmbAddlGeoField.setLayer(layer)

    def fieldChanged(self, field):
        self.btnAddAddlGeoField.setEnabled(field != '' and (
            not self.cmbAddlGeoField.isExpression() or self.cmbAddlGeoField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.cmbAddlGeoField.currentField()
        if not isValid:
            return

        layer = self.field('sourceLayer')
        self.fieldsModel.appendField(layer, field, isExpression)
