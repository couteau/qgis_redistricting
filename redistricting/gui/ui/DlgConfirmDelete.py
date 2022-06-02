# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/DlgConfirmDelete.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_dlgConfirmDelete(object):
    def setupUi(self, dlgConfirmDelete):
        dlgConfirmDelete.setObjectName("dlgConfirmDelete")
        dlgConfirmDelete.resize(282, 145)
        self.verticalLayout = QtWidgets.QVBoxLayout(dlgConfirmDelete)
        self.verticalLayout.setObjectName("verticalLayout")
        self.lblConfirm = QtWidgets.QLabel(dlgConfirmDelete)
        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(24)
        font.setBold(True)
        font.setWeight(75)
        self.lblConfirm.setFont(font)
        self.lblConfirm.setAlignment(QtCore.Qt.AlignCenter)
        self.lblConfirm.setObjectName("lblConfirm")
        self.verticalLayout.addWidget(self.lblConfirm)
        self.cbxRemoveLayers = QtWidgets.QCheckBox(dlgConfirmDelete)
        self.cbxRemoveLayers.setChecked(True)
        self.cbxRemoveLayers.setObjectName("cbxRemoveLayers")
        self.verticalLayout.addWidget(self.cbxRemoveLayers)
        self.cbxDeleteLayers = QtWidgets.QCheckBox(dlgConfirmDelete)
        self.cbxDeleteLayers.setObjectName("cbxDeleteLayers")
        self.verticalLayout.addWidget(self.cbxDeleteLayers)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(dlgConfirmDelete)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(dlgConfirmDelete)
        self.buttonBox.accepted.connect(dlgConfirmDelete.accept)
        self.buttonBox.rejected.connect(dlgConfirmDelete.reject)
        self.cbxRemoveLayers.toggled['bool'].connect(self.cbxDeleteLayers.setEnabled)
        QtCore.QMetaObject.connectSlotsByName(dlgConfirmDelete)

    def retranslateUi(self, dlgConfirmDelete):
        _translate = QtCore.QCoreApplication.translate
        dlgConfirmDelete.setWindowTitle(_translate("dlgConfirmDelete", "Confirm Delete"))
        self.lblConfirm.setText(_translate("dlgConfirmDelete", "Really delete plan?"))
        self.cbxRemoveLayers.setText(_translate("dlgConfirmDelete", "Remove plan layers from project"))
        self.cbxDeleteLayers.setText(_translate("dlgConfirmDelete", "Delete plan GeoPackage from disk"))
