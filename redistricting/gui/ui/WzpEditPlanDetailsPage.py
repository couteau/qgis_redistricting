# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/WzpEditPlanDetailsPage.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from qgis import gui
from qgis.PyQt import (
    QtCore,
    QtGui,
    QtWidgets
)

from .RedistrictingWidgets import RdsFileWidget


class Ui_wzpPlanDetails(object):
    def setupUi(self, wzpPlanDetails):
        wzpPlanDetails.setObjectName("wzpPlanDetails")
        wzpPlanDetails.resize(605, 406)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(wzpPlanDetails.sizePolicy().hasHeightForWidth())
        wzpPlanDetails.setSizePolicy(sizePolicy)
        self.gridLayout = QtWidgets.QGridLayout(wzpPlanDetails)
        self.gridLayout.setObjectName("gridLayout")
        self.inpPlanName = QtWidgets.QLineEdit(wzpPlanDetails)
        self.inpPlanName.setObjectName("inpPlanName")
        self.gridLayout.addWidget(self.inpPlanName, 0, 1, 1, 1)
        self.txtDescription = QtWidgets.QPlainTextEdit(wzpPlanDetails)
        self.txtDescription.setTabChangesFocus(True)
        self.txtDescription.setObjectName("txtDescription")
        self.gridLayout.addWidget(self.txtDescription, 6, 0, 1, 2)
        self.lblNumDistricts = QtWidgets.QLabel(wzpPlanDetails)
        self.lblNumDistricts.setObjectName("lblNumDistricts")
        self.gridLayout.addWidget(self.lblNumDistricts, 2, 0, 1, 1)
        self.lblNumSeats = QtWidgets.QLabel(wzpPlanDetails)
        self.lblNumSeats.setObjectName("lblNumSeats")
        self.gridLayout.addWidget(self.lblNumSeats, 3, 0, 1, 1)
        self.sbxNumDistricts = QtWidgets.QSpinBox(wzpPlanDetails)
        self.sbxNumDistricts.setMinimum(1)
        self.sbxNumDistricts.setMaximum(1000)
        self.sbxNumDistricts.setObjectName("sbxNumDistricts")
        self.gridLayout.addWidget(self.sbxNumDistricts, 2, 1, 1, 1)
        self.lblDescription = QtWidgets.QLabel(wzpPlanDetails)
        self.lblDescription.setObjectName("lblDescription")
        self.gridLayout.addWidget(self.lblDescription, 5, 0, 1, 1)
        self.sbxNumSeats = QtWidgets.QSpinBox(wzpPlanDetails)
        self.sbxNumSeats.setMinimum(1)
        self.sbxNumSeats.setMaximum(1000)
        self.sbxNumSeats.setProperty("value", 1)
        self.sbxNumSeats.setObjectName("sbxNumSeats")
        self.gridLayout.addWidget(self.sbxNumSeats, 3, 1, 1, 1)
        self.lblPlanName = QtWidgets.QLabel(wzpPlanDetails)
        self.lblPlanName.setObjectName("lblPlanName")
        self.gridLayout.addWidget(self.lblPlanName, 0, 0, 1, 1)
        self.fileGpkg = RdsFileWidget(wzpPlanDetails)
        self.fileGpkg.setFilter("*.gpkg")
        self.fileGpkg.setStorageMode(gui.QgsFileWidget.SaveFile)
        self.fileGpkg.setObjectName("fileGpkg")
        self.gridLayout.addWidget(self.fileGpkg, 1, 1, 1, 1)
        self.lblGpkg = QtWidgets.QLabel(wzpPlanDetails)
        self.lblGpkg.setObjectName("lblGpkg")
        self.gridLayout.addWidget(self.lblGpkg, 1, 0, 1, 1)
        self.lblNumDistricts.setBuddy(self.sbxNumDistricts)
        self.lblNumSeats.setBuddy(self.sbxNumSeats)
        self.lblDescription.setBuddy(self.txtDescription)
        self.lblPlanName.setBuddy(self.inpPlanName)
        self.lblGpkg.setBuddy(self.fileGpkg)

        self.retranslateUi(wzpPlanDetails)
        QtCore.QMetaObject.connectSlotsByName(wzpPlanDetails)
        wzpPlanDetails.setTabOrder(self.inpPlanName, self.sbxNumDistricts)
        wzpPlanDetails.setTabOrder(self.sbxNumDistricts, self.sbxNumSeats)
        wzpPlanDetails.setTabOrder(self.sbxNumSeats, self.txtDescription)

    def retranslateUi(self, wzpPlanDetails):
        _translate = QtCore.QCoreApplication.translate
        wzpPlanDetails.setWindowTitle(_translate("wzpPlanDetails", "Plan Details"))
        wzpPlanDetails.setTitle(_translate("wzpPlanDetails", "Plan Details"))
        wzpPlanDetails.setSubTitle(_translate(
            "wzpPlanDetails", "Configure plan name, GeoPackage, number of districts, number of members, and description"))
        self.inpPlanName.setToolTip(_translate("wzpPlanDetails", "Enter a name for your districting plan"))
        self.lblNumDistricts.setText(_translate("wzpPlanDetails", "&Number of Districts"))
        self.lblNumSeats.setText(_translate("wzpPlanDetails", "Number of &Seats"))
        self.sbxNumDistricts.setToolTip(_translate(
            "wzpPlanDetails", "Enter the total number of districts in your plan"))
        self.lblDescription.setText(_translate("wzpPlanDetails", "Plan &Description"))
        self.sbxNumSeats.setToolTip(_translate(
            "wzpPlanDetails", "Enter the number of seats that are elected from the districts in this plan"))
        self.lblPlanName.setText(_translate("wzpPlanDetails", "Plan Na&me"))
        self.fileGpkg.setToolTip(_translate(
            "wzpPlanDetails", "Enter the path to a new GeoPackage in which to store geography assignments and district summary"))
        self.fileGpkg.setDialogTitle(_translate("wzpPlanDetails", "Plan GeoPackage File"))
        self.lblGpkg.setText(_translate("wzpPlanDetails", "GeoPackage &Path"))
