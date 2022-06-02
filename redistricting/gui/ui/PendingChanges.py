# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/redistricting/redistricting/ui/PendingChanges.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_qdwPendingChanges(object):
    def setupUi(self, qdwPendingChanges):
        qdwPendingChanges.setObjectName("qdwPendingChanges")
        qdwPendingChanges.resize(271, 444)
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.gridLayout = QtWidgets.QGridLayout(self.dockWidgetContents)
        self.gridLayout.setObjectName("gridLayout")
        self.tblPending = QtWidgets.QTableView(self.dockWidgetContents)
        self.tblPending.setStyleSheet("QHeaderView::section {padding-right: 5px;}")
        self.tblPending.setCornerButtonEnabled(False)
        self.tblPending.setObjectName("tblPending")
        self.gridLayout.addWidget(self.tblPending, 0, 0, 1, 1)
        qdwPendingChanges.setWidget(self.dockWidgetContents)

        self.retranslateUi(qdwPendingChanges)
        QtCore.QMetaObject.connectSlotsByName(qdwPendingChanges)

    def retranslateUi(self, qdwPendingChanges):
        _translate = QtCore.QCoreApplication.translate
        qdwPendingChanges.setWindowTitle(_translate("qdwPendingChanges", "Pending Changes"))
