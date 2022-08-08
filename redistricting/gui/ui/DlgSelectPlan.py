# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/qgis_redistricting/ui/DlgSelectPlan.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_dlgSelectPlan(object):
    def setupUi(self, dlgSelectPlan):
        dlgSelectPlan.setObjectName("dlgSelectPlan")
        dlgSelectPlan.resize(435, 381)
        self.verticalLayout = QtWidgets.QVBoxLayout(dlgSelectPlan)
        self.verticalLayout.setObjectName("verticalLayout")
        self.lvwPlans = QtWidgets.QTableView(dlgSelectPlan)
        self.lvwPlans.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.lvwPlans.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.lvwPlans.setShowGrid(False)
        self.lvwPlans.setWordWrap(False)
        self.lvwPlans.setObjectName("lvwPlans")
        self.lvwPlans.horizontalHeader().setStretchLastSection(True)
        self.lvwPlans.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.lvwPlans)
        self.gridLayout = QtWidgets.QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.btnEdit = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnEdit.setObjectName("btnEdit")
        self.gridLayout.addWidget(self.btnEdit, 2, 3, 1, 1)
        self.btnCancel = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnCancel.setObjectName("btnCancel")
        self.gridLayout.addWidget(self.btnCancel, 2, 5, 1, 1)
        self.btnOpen = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnOpen.setEnabled(False)
        self.btnOpen.setDefault(True)
        self.btnOpen.setObjectName("btnOpen")
        self.gridLayout.addWidget(self.btnOpen, 2, 0, 1, 1)
        self.btnDelete = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnDelete.setObjectName("btnDelete")
        self.gridLayout.addWidget(self.btnDelete, 2, 4, 1, 1)
        self.btnNew = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnNew.setObjectName("btnNew")
        self.gridLayout.addWidget(self.btnNew, 2, 1, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)

        self.retranslateUi(dlgSelectPlan)
        QtCore.QMetaObject.connectSlotsByName(dlgSelectPlan)

    def retranslateUi(self, dlgSelectPlan):
        _translate = QtCore.QCoreApplication.translate
        dlgSelectPlan.setWindowTitle(_translate("dlgSelectPlan", "Select Redistricting Plan"))
        self.btnEdit.setText(_translate("dlgSelectPlan", "Edit"))
        self.btnCancel.setText(_translate("dlgSelectPlan", "Close"))
        self.btnOpen.setText(_translate("dlgSelectPlan", "Select"))
        self.btnDelete.setText(_translate("dlgSelectPlan", "Delete"))
        self.btnNew.setText(_translate("dlgSelectPlan", "New "))
