# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/Users/stuart/Source/redistricting/redistricting/ui/DistrictDataTable.ui'
#
# Created by: PyQt5 UI code generator 5.12.3
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_qdwDistrictData(object):
    def setupUi(self, qdwDistrictData):
        qdwDistrictData.setObjectName("qdwDistrictData")
        qdwDistrictData.resize(400, 300)
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.gridLayout = QtWidgets.QGridLayout(self.dockWidgetContents)
        self.gridLayout.setObjectName("gridLayout")
        self.tblDataTable = QtWidgets.QTableView(self.dockWidgetContents)
        self.tblDataTable.setObjectName("tblDataTable")
        self.gridLayout.addWidget(self.tblDataTable, 2, 1, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtWidgets.QLabel(self.dockWidgetContents)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.lblPlanName = QtWidgets.QLabel(self.dockWidgetContents)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.lblPlanName.setFont(font)
        self.lblPlanName.setObjectName("lblPlanName")
        self.horizontalLayout.addWidget(self.lblPlanName)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.frame = QtWidgets.QFrame(self.dockWidgetContents)
        self.frame.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.frame.setFrameShadow(QtWidgets.QFrame.Plain)
        self.frame.setObjectName("frame")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.frame)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setSpacing(4)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.btnCopy = QtWidgets.QToolButton(self.frame)
        self.btnCopy.setObjectName("btnCopy")
        self.horizontalLayout_2.addWidget(self.btnCopy)
        self.btnRecalculate = QtWidgets.QToolButton(self.frame)
        self.btnRecalculate.setObjectName("btnRecalculate")
        self.horizontalLayout_2.addWidget(self.btnRecalculate)
        self.btnAddFields = QtWidgets.QToolButton(self.frame)
        self.btnAddFields.setObjectName("btnAddFields")
        self.horizontalLayout_2.addWidget(self.btnAddFields)
        self.horizontalLayout.addWidget(self.frame)
        self.gridLayout.addLayout(self.horizontalLayout, 0, 1, 1, 1)
        qdwDistrictData.setWidget(self.dockWidgetContents)

        self.retranslateUi(qdwDistrictData)
        QtCore.QMetaObject.connectSlotsByName(qdwDistrictData)

    def retranslateUi(self, qdwDistrictData):
        _translate = QtCore.QCoreApplication.translate
        qdwDistrictData.setWindowTitle(_translate("qdwDistrictData", "QGIS Redistricting - Plan Analysis"))
        self.label.setText(_translate("qdwDistrictData", "Redistricting Plan"))
        self.lblPlanName.setText(_translate("qdwDistrictData", "No plan selected"))
        self.btnCopy.setToolTip(_translate("qdwDistrictData", "Copy entire table to clipboard"))
        self.btnCopy.setText(_translate("qdwDistrictData", "..."))
        self.btnRecalculate.setToolTip(_translate("qdwDistrictData", "Recalculate"))
        self.btnRecalculate.setStatusTip(_translate("qdwDistrictData", "Reaggregate all demographics"))
        self.btnRecalculate.setText(_translate("qdwDistrictData", "..."))
        self.btnAddFields.setToolTip(_translate("qdwDistrictData", "Add or edit data fields"))
        self.btnAddFields.setText(_translate("qdwDistrictData", "..."))
