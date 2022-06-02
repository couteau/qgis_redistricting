# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Redistricting Plugin New Plan Wizard - Population Page

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
import re
from qgis.core import QgsVectorLayer
from qgis.PyQt.QtWidgets import QWizardPage
from .ui.WzpEditPlanPopPage import Ui_wzpPopulation


class dlgEditPlanPopPage(Ui_wzpPopulation, QWizardPage):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.registerField('popLayer', self.cmbPopLayer)
        self.registerField('joinField', self.cmbJoinField)
        self.registerField('popField*', self.cmbPopField)
        self.registerField('deviation', self.sbxMaxDeviation,
                           'value', self.sbxMaxDeviation.valueChanged)
        self.registerField('vapField', self.cmbVAPField)
        self.registerField('cvapField', self.cmbCVAPField)

        # Annoyingly, loading the UI sets the layer property of a QgsLayerCombo to
        # the first layer in the project, even if allowEmptyLayer is set to true.
        # Clear it to put it into a sane default state.
        self.cmbPopLayer.setLayer(None)

        self.cmbPopLayer.layerChanged.connect(self.setPopLayer)
        self.btnUseGeoLayer.toggled.connect(self.updatePopLayer)

        self.setFinalPage(True)

    def initializePage(self):
        super().initializePage()
        popLayer = self.field('popLayer') or None
        sourceLayer = self.field('sourceLayer') or None
        if popLayer is None:
            popLayer = sourceLayer
        joinField = self.field('joinField')
        geoIdField = self.field('geoIdField')

        if popLayer == sourceLayer:
            self.btnUseGeoLayer.setChecked(True)
        else:
            self.btnOtherPopLayer.setChecked(True)

        self.cmbJoinField.setLayer(popLayer)
        if joinField is None and popLayer and popLayer.fields().lookupField(geoIdField) != -1:
            self.cmbJoinField.setField(geoIdField)
        self.cmbPopLayer.setLayer(popLayer)
        self.cmbPopField.setLayer(popLayer)
        self.cmbVAPField.setLayer(popLayer)
        self.cmbCVAPField.setLayer(popLayer)
        self.setPopLayer(popLayer)
        self.cmbPopField.setFocus()

    def updatePopLayer(self):
        if self.btnUseGeoLayer.isChecked():
            sourceLayer = self.field('sourceLayer') or None
            self.cmbPopLayer.setLayer(sourceLayer)

    def setPopLayer(self, layer: QgsVectorLayer):
        if not layer:
            return

        if not self.field('popField'):
            if layer.fields().indexFromName('pop_total') != -1:
                self.cmbPopField.setField('pop_total')
            elif layer.fields().indexFromName('p0010001') != -1:
                self.cmbPopField.setField('p0010001')
            elif layer.fields().indexFromName('P0010001') != -1:
                self.cmbPopField.setField('P0010001')

        if not self.field('vapField'):
            if layer.fields().indexFromName('vap_total') != -1:
                self.cmbVAPField.setField('vap_total')
            elif layer.fields().indexFromName('p0030001') != -1:
                self.cmbVAPField.setField('p0030001')
            elif layer.fields().indexFromName('P0030001') != -1:
                self.cmbVAPField.setField('P0030001')

        if not self.field('cvapField'):
            if layer.fields().indexFromName('cvap_total') != -1:
                self.cmbCVAPField.setField('cvap_total')
            regex = re.compile(r'^cvap_(?:\d{4}_)total$')
            for f in layer.fields():
                if regex.match(f.name()):
                    self.cmbCVAPField.setField(f.name())
