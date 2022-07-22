# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/WzpEditPlanGeoPage.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_wzpAddlGeography(object):
    def setupUi(self, wzpAddlGeography):
        wzpAddlGeography.setObjectName("wzpAddlGeography")
        wzpAddlGeography.resize(603, 408)
        self.gridLayout = QtWidgets.QGridLayout(wzpAddlGeography)
        self.gridLayout.setObjectName("gridLayout")
        self.cmbGeoCaption = QtWidgets.QComboBox(wzpAddlGeography)
        self.cmbGeoCaption.setEditable(True)
        self.cmbGeoCaption.setInsertPolicy(QtWidgets.QComboBox.InsertAlphabetically)
        self.cmbGeoCaption.setObjectName("cmbGeoCaption")
        self.gridLayout.addWidget(self.cmbGeoCaption, 2, 1, 1, 2)
        self.groupBox = QtWidgets.QGroupBox(wzpAddlGeography)
        self.groupBox.setFlat(False)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.cmbAddlGeoField = gui.QgsFieldExpressionWidget(self.groupBox)
        self.cmbAddlGeoField.setObjectName("cmbAddlGeoField")
        self.gridLayout_2.addWidget(self.cmbAddlGeoField, 0, 0, 1, 1)
        self.btnAddAddlGeoField = QtWidgets.QToolButton(self.groupBox)
        self.btnAddAddlGeoField.setObjectName("btnAddAddlGeoField")
        self.gridLayout_2.addWidget(self.btnAddAddlGeoField, 0, 1, 1, 1)
        self.tblAddlGeography = RdsFieldTableView(self.groupBox)
        self.tblAddlGeography.setAlternatingRowColors(True)
        self.tblAddlGeography.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tblAddlGeography.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tblAddlGeography.setObjectName("tblAddlGeography")
        self.tblAddlGeography.horizontalHeader().setStretchLastSection(True)
        self.gridLayout_2.addWidget(self.tblAddlGeography, 1, 0, 1, 2)
        self.gridLayout.addWidget(self.groupBox, 3, 0, 1, 3)
        self.lblGeoLayer = QtWidgets.QLabel(wzpAddlGeography)
        self.lblGeoLayer.setObjectName("lblGeoLayer")
        self.gridLayout.addWidget(self.lblGeoLayer, 0, 0, 1, 1)
        self.cmbSourceLayer = RdsMapLayerComboBox(wzpAddlGeography)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cmbSourceLayer.sizePolicy().hasHeightForWidth())
        self.cmbSourceLayer.setSizePolicy(sizePolicy)
        self.cmbSourceLayer.setObjectName("cmbSourceLayer")
        self.gridLayout.addWidget(self.cmbSourceLayer, 0, 1, 1, 2)
        self.lblGeoCaption = QtWidgets.QLabel(wzpAddlGeography)
        self.lblGeoCaption.setObjectName("lblGeoCaption")
        self.gridLayout.addWidget(self.lblGeoCaption, 2, 0, 1, 1)
        self.lblGeoIDField = QtWidgets.QLabel(wzpAddlGeography)
        self.lblGeoIDField.setObjectName("lblGeoIDField")
        self.gridLayout.addWidget(self.lblGeoIDField, 1, 0, 1, 1)
        self.cmbGeoIDField = RdsFieldComboBox(wzpAddlGeography)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cmbGeoIDField.sizePolicy().hasHeightForWidth())
        self.cmbGeoIDField.setSizePolicy(sizePolicy)
        self.cmbGeoIDField.setObjectName("cmbGeoIDField")
        self.gridLayout.addWidget(self.cmbGeoIDField, 1, 1, 1, 2)
        self.lblGeoLayer.setBuddy(self.cmbSourceLayer)
        self.lblGeoIDField.setBuddy(self.cmbGeoIDField)

        self.retranslateUi(wzpAddlGeography)
        QtCore.QMetaObject.connectSlotsByName(wzpAddlGeography)

    def retranslateUi(self, wzpAddlGeography):
        _translate = QtCore.QCoreApplication.translate
        wzpAddlGeography.setWindowTitle(_translate("wzpAddlGeography", "Geography"))
        wzpAddlGeography.setTitle(_translate("wzpAddlGeography", "Geography"))
        wzpAddlGeography.setSubTitle(_translate("wzpAddlGeography", "Define units of geography from which the districting plan will be built"))
        self.groupBox.setToolTip(_translate("wzpAddlGeography", "Add additional levels of geography from which districts can be built"))
        self.groupBox.setTitle(_translate("wzpAddlGeography", "Additional Geography"))
        self.btnAddAddlGeoField.setText(_translate("wzpAddlGeography", "..."))
        self.lblGeoLayer.setText(_translate("wzpAddlGeography", "Import Geography from Layer"))
        self.cmbSourceLayer.setToolTip(_translate("wzpAddlGeography", "Select layer from which geography will be imported (e.g., census blocks, vtds)"))
        self.lblGeoCaption.setText(_translate("wzpAddlGeography", "Geography Name"))
        self.lblGeoIDField.setText(_translate("wzpAddlGeography", "Primary Geography ID Field"))
        self.cmbGeoIDField.setToolTip(_translate("wzpAddlGeography", "Field containing unique identifier for smallest unit of geography"))
from qgis import gui
from .RedistrictingWidgets import RdsFieldComboBox, RdsFieldTableView, RdsMapLayerComboBox
