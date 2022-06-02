# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/WzpEditPlanFieldPage.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_wzpDisplayFields(object):
    def setupUi(self, wzpDisplayFields):
        wzpDisplayFields.setObjectName("wzpDisplayFields")
        wzpDisplayFields.resize(571, 381)
        self.gridLayout = QtWidgets.QGridLayout(wzpDisplayFields)
        self.gridLayout.setObjectName("gridLayout")
        self.btnAddField = QtWidgets.QToolButton(wzpDisplayFields)
        self.btnAddField.setEnabled(False)
        self.btnAddField.setText("")
        icon = QtGui.QIcon.fromTheme("list-add")
        self.btnAddField.setIcon(icon)
        self.btnAddField.setObjectName("btnAddField")
        self.gridLayout.addWidget(self.btnAddField, 1, 1, 1, 1)
        self.fexDataField = gui.QgsFieldExpressionWidget(wzpDisplayFields)
        self.fexDataField.setObjectName("fexDataField")
        self.gridLayout.addWidget(self.fexDataField, 1, 0, 1, 1)
        self.tblDataFields = RdsFieldTableView(wzpDisplayFields)
        self.tblDataFields.setAlternatingRowColors(True)
        self.tblDataFields.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tblDataFields.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tblDataFields.setObjectName("tblDataFields")
        self.tblDataFields.horizontalHeader().setStretchLastSection(True)
        self.gridLayout.addWidget(self.tblDataFields, 2, 0, 1, 2)

        self.retranslateUi(wzpDisplayFields)
        QtCore.QMetaObject.connectSlotsByName(wzpDisplayFields)
        wzpDisplayFields.setTabOrder(self.btnAddField, self.tblDataFields)

    def retranslateUi(self, wzpDisplayFields):
        _translate = QtCore.QCoreApplication.translate
        wzpDisplayFields.setWindowTitle(_translate("wzpDisplayFields", "Additional Population Fields"))
        wzpDisplayFields.setTitle(_translate("wzpDisplayFields", "Additional Population Fields"))
        wzpDisplayFields.setSubTitle(_translate("wzpDisplayFields", "Configure additional fields from the population layer for district analysis"))
        self.fexDataField.setExpressionDialogTitle(_translate("wzpDisplayFields", "Define Expression"))
from qgis import gui
from .RedistrictingWidgets import RdsFieldTableView
