# -*- coding: utf-8 -*-
"""QGIS Redistricting Plugin - New/Edit Plan Wizard - Population Page

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
    QgsFieldProxyModel,
    QgsVectorLayer
)
from qgis.PyQt.QtWidgets import (
    QHeaderView,
    QWizardPage
)

from ..models import RdsField
from ..services import defaults
from ..utils import getDefaultField
from .ui.WzpEditPlanPopPage import Ui_wzpPopulation


class dlgEditPlanPopPage(Ui_wzpPopulation, QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.registerField('popLayer', self.cmbPopLayer)
        self.registerField('joinField', self.cmbJoinField)
        self.registerField('popField*', self.cmbPopField)
        self.registerField('deviation', self.sbxMaxDeviation, 'value', self.sbxMaxDeviation.valueChanged)
        self.registerField('popFields', self.tblAddlPopulation, 'fields', self.tblAddlPopulation.fieldsChanged)

        self.fieldsModel = self.tblAddlPopulation.model()

        # Annoyingly, loading the UI sets the layer property of a QgsLayerCombo to
        # the first layer in the project, even if allowEmptyLayer is set to true.
        # Clear it to put it into a sane default state.
        self.cmbPopLayer.setLayer(None)

        self.cmbPopLayer.layerChanged.connect(self.setPopLayer)
        self.btnUseGeoLayer.toggled.connect(self.updatePopLayer)

        self.cmbPopField.setFilters(QgsFieldProxyModel.Numeric)
        self.cmbAddlPopField.setFilters(QgsFieldProxyModel.Numeric)
        self.cmbAddlPopField.fieldChanged.connect(self.fieldChanged)
        self.btnAddAddlPopField.setIcon(QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.btnAddAddlPopField.clicked.connect(self.addField)

        self.tblAddlPopulation.setEnableDragRows(True)
        self.tblAddlPopulation.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tblAddlPopulation.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tblAddlPopulation.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.setFinalPage(True)

    def initializePage(self):
        super().initializePage()
        popLayer = self.field('popLayer') or None
        geoLayer = self.field('sourceLayer') or None
        if popLayer is None:
            popLayer = geoLayer

        if popLayer == geoLayer:
            self.btnUseGeoLayer.setChecked(True)
        else:
            self.btnOtherPopLayer.setChecked(True)

        self.cmbPopLayer.setLayer(popLayer)
        self.setPopLayer(popLayer)
        self.cmbAddlPopField.setLayer(popLayer)
        self.cmbPopField.setFocus()
        self.setFinalPage(self.wizard().isComplete())

    def cleanupPage(self):
        ...

    def updatePopLayer(self):
        if self.btnUseGeoLayer.isChecked():
            geoLayer = self.field('sourceLayer') or None
            self.cmbPopLayer.setLayer(geoLayer)

    def setPopLayer(self, layer: QgsVectorLayer):
        if not layer:
            self.cmbJoinField.setLayer(None)
            self.cmbPopField.setLayer(None)
            self.cmbAddlPopField.setLayer(None)
            return

        if layer != self.cmbJoinField.layer():
            joinField = self.field('joinField')
            geoIdField = self.field('geoIdField')
            self.cmbJoinField.setLayer(layer)
            if joinField and layer.fields().lookupField(joinField) != -1:
                self.cmbJoinField.setField(joinField)
            elif layer.fields().lookupField(geoIdField) != -1:
                self.cmbJoinField.setField(geoIdField)

            popField = self.field('popField')
            self.cmbPopField.setLayer(layer)
            if popField and layer.fields().lookupField(popField) != -1:
                self.cmbPopField.setField(popField)
            else:
                self.cmbPopField.setField(getDefaultField(layer, defaults.POP_TOTAL_FIELDS))

            self.cmbAddlPopField.setLayer(layer)
            popFields: list[RdsField] = self.field('popFields')
            for f in popFields:
                f.setLayer(layer)

    def fieldChanged(self, field):
        self.btnAddAddlPopField.setEnabled(field != '' and (
            not self.cmbAddlPopField.isExpression() or self.cmbAddlPopField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.cmbAddlPopField.currentField()
        if not isValid:
            return

        layer = self.field('popLayer')
        self.fieldsModel.appendField(layer, field, isExpression)
