# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/redistricting/redistricting/ui/DlgSelectPlan.ui'
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
        self.btnCancel = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnCancel.setObjectName("btnCancel")
        self.gridLayout.addWidget(self.btnCancel, 1, 5, 1, 1)
        self.btnEdit = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnEdit.setObjectName("btnEdit")
        self.gridLayout.addWidget(self.btnEdit, 1, 3, 1, 1)
        self.btnOpen = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnOpen.setEnabled(False)
        self.btnOpen.setDefault(True)
        self.btnOpen.setObjectName("btnOpen")
        self.gridLayout.addWidget(self.btnOpen, 1, 0, 1, 1)
        self.btnDelete = QtWidgets.QPushButton(dlgSelectPlan)
        self.btnDelete.setObjectName("btnDelete")
        self.gridLayout.addWidget(self.btnDelete, 1, 4, 1, 1)
        self.verticalLayout.addLayout(self.gridLayout)

        self.retranslateUi(dlgSelectPlan)
        QtCore.QMetaObject.connectSlotsByName(dlgSelectPlan)

    def retranslateUi(self, dlgSelectPlan):
        _translate = QtCore.QCoreApplication.translate
        dlgSelectPlan.setWindowTitle(_translate("dlgSelectPlan", "Select Redistricting Plan"))
        self.btnCancel.setText(_translate("dlgSelectPlan", "Close"))
        self.btnEdit.setText(_translate("dlgSelectPlan", "Edit"))
        self.btnOpen.setText(_translate("dlgSelectPlan", "Select"))
        self.btnDelete.setText(_translate("dlgSelectPlan", "Delete"))
