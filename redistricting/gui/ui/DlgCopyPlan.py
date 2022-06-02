# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/DlgCopyPlan.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_dlgCopyPlan(object):
    def setupUi(self, dlgCopyPlan):
        dlgCopyPlan.setObjectName("dlgCopyPlan")
        dlgCopyPlan.resize(482, 176)
        self.gridLayout = QtWidgets.QGridLayout(dlgCopyPlan)
        self.gridLayout.setObjectName("gridLayout")
        self.lblPlanName = QtWidgets.QLabel(dlgCopyPlan)
        self.lblPlanName.setObjectName("lblPlanName")
        self.gridLayout.addWidget(self.lblPlanName, 1, 0, 1, 1)
        self.inpPlanName = QtWidgets.QLineEdit(dlgCopyPlan)
        self.inpPlanName.setObjectName("inpPlanName")
        self.gridLayout.addWidget(self.inpPlanName, 1, 1, 1, 2)
        self.fwGeoPackage = RdsFileWidget(dlgCopyPlan)
        self.fwGeoPackage.setFilter("*.gpkg")
        self.fwGeoPackage.setObjectName("fwGeoPackage")
        self.gridLayout.addWidget(self.fwGeoPackage, 2, 1, 1, 2)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem, 4, 0, 1, 3)
        self.buttonBox = QtWidgets.QDialogButtonBox(dlgCopyPlan)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 5, 2, 1, 1)
        self.lblSourcePlan = QtWidgets.QLabel(dlgCopyPlan)
        self.lblSourcePlan.setObjectName("lblSourcePlan")
        self.gridLayout.addWidget(self.lblSourcePlan, 0, 0, 1, 3)
        self.cbxCopyAssignments = QtWidgets.QCheckBox(dlgCopyPlan)
        self.cbxCopyAssignments.setChecked(True)
        self.cbxCopyAssignments.setObjectName("cbxCopyAssignments")
        self.gridLayout.addWidget(self.cbxCopyAssignments, 3, 0, 1, 3)
        self.lblGeoPackage = QtWidgets.QLabel(dlgCopyPlan)
        self.lblGeoPackage.setObjectName("lblGeoPackage")
        self.gridLayout.addWidget(self.lblGeoPackage, 2, 0, 1, 1)
        self.lblGeoPackage.setBuddy(self.fwGeoPackage)

        self.retranslateUi(dlgCopyPlan)
        self.buttonBox.accepted.connect(dlgCopyPlan.accept)
        self.buttonBox.rejected.connect(dlgCopyPlan.reject)
        QtCore.QMetaObject.connectSlotsByName(dlgCopyPlan)

    def retranslateUi(self, dlgCopyPlan):
        _translate = QtCore.QCoreApplication.translate
        dlgCopyPlan.setWindowTitle(_translate("dlgCopyPlan", "Copy Redistricting Plan"))
        self.lblPlanName.setText(_translate("dlgCopyPlan", "New Plan Name"))
        self.lblSourcePlan.setText(_translate("dlgCopyPlan", "Copy Plan from"))
        self.cbxCopyAssignments.setText(_translate("dlgCopyPlan", "Copy assignments"))
        self.lblGeoPackage.setText(_translate("dlgCopyPlan", "GeoPackage Path"))
from .RedistrictingWidgets import RdsFileWidget
