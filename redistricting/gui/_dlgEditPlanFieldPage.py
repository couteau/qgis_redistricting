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
from qgis.PyQt.QtCore import QModelIndex
from qgis.PyQt.QtWidgets import QWizardPage
from qgis.core import QgsApplication
from ..core import DataField
from .ui.WzpEditPlanFieldPage import Ui_wzpDisplayFields


class dlgEditPlanFieldPage(Ui_wzpDisplayFields, QWizardPage):
    fields = None

    def __init__(self,  parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.fieldsModel = self.tblDataFields.model()
        self.fieldsModel.fieldType = DataField
        #self.fieldsModel = DataFieldsModel(self)
        # self.tblDataFields.setModel(self.fieldsModel)

        self.registerField('dataFields', self.tblDataFields)
        self.tblDataFields.setEnableDragRows(True)

        self.btnAddField.setIcon(
            QgsApplication.getThemeIcon('/mActionAdd.svg'))
        self.fexDataField.fieldChanged.connect(self.fieldChanged)
        self.btnAddField.clicked.connect(self.addField)
        self.tblDataFields.clicked.connect(self.deleteField)

    def initializePage(self):
        super().initializePage()
        self.tblDataFields.setColumnWidth(0, 120)
        self.tblDataFields.setColumnWidth(1, 120)
        self.tblDataFields.setColumnWidth(2, 30)
        self.tblDataFields.setColumnWidth(3, 48)
        self.tblDataFields.setColumnWidth(4, 48)
        self.tblDataFields.setColumnWidth(5, 48)
        self.tblDataFields.setColumnWidth(6, 32)
        self.fexDataField.setLayer(self.field('popLayer') or self.field('sourceLayer'))
        self.fieldsModel.vapEnabled = bool(self.field('vapField'))
        self.fieldsModel.cvapEnabled = bool(self.field('cvapField'))
        self.setFinalPage(self.parent().isComplete())

    def cleanupPage(self):
        ...

    def fieldChanged(self, field):
        self.btnAddField.setEnabled(field != '' and (
            not self.fexDataField.isExpression() or self.fexDataField.isValidExpression()))

    def addField(self):
        field, isExpression, isValid = self.fexDataField.currentField()
        if not isValid:
            return

        layer = self.field('popLayer') or self.field('sourceLayer')
        self.fieldsModel.appendField(layer, field, isExpression)

    def deleteField(self, index: QModelIndex):
        if index.column() == 6:
            self.fieldsModel.deleteField(index.row())
